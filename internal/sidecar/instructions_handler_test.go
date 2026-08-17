package sidecar

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strconv"
	"testing"
)

// newInstructionsServer returns a tokenless server with cam.db, config dir and
// HOME isolated to temp directories so instruction files never touch real home.
func newInstructionsServer(t *testing.T) http.Handler {
	t.Helper()
	dir := t.TempDir()
	home := t.TempDir()
	t.Setenv("CAM_CONFIG_DIR", dir)
	t.Setenv("CAM_DB_PATH", filepath.Join(dir, "cam.db"))
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)
	return New(Options{Version: "test"}).Handler()
}

func doJSON(t *testing.T, handler http.Handler, method, path, body string) *httptest.ResponseRecorder {
	t.Helper()
	var rdr *bytes.Buffer
	if body != "" {
		rdr = bytes.NewBufferString(body)
	} else {
		rdr = bytes.NewBuffer(nil)
	}
	req := httptest.NewRequest(method, path, rdr)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	return rec
}

func TestInstructionsCRUDEndpoints(t *testing.T) {
	handler := newInstructionsServer(t)

	// Empty list.
	rec := doJSON(t, handler, http.MethodGet, "/api/instructions", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("list status=%d body=%s", rec.Code, rec.Body.String())
	}
	if got := rec.Body.String(); got != "[]\n" {
		t.Fatalf("empty list = %q", got)
	}

	// Create.
	rec = doJSON(t, handler, http.MethodPost, "/api/instructions", `{"name":"Instruction01","description":"d","content":"# hi"}`)
	if rec.Code != http.StatusCreated {
		t.Fatalf("create status=%d body=%s", rec.Code, rec.Body.String())
	}
	var created map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &created); err != nil {
		t.Fatalf("create json: %v", err)
	}
	id := int64(created["id"].(float64))

	// Duplicate name -> 409.
	rec = doJSON(t, handler, http.MethodPost, "/api/instructions", `{"name":"Instruction01"}`)
	if rec.Code != http.StatusConflict {
		t.Fatalf("dup status=%d, want 409", rec.Code)
	}

	// Invalid name -> 400.
	rec = doJSON(t, handler, http.MethodPost, "/api/instructions", `{"name":"a/b"}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("invalid name status=%d, want 400", rec.Code)
	}

	// Get.
	rec = doJSON(t, handler, http.MethodGet, "/api/instructions/"+strconv.FormatInt(id, 10), "")
	if rec.Code != http.StatusOK {
		t.Fatalf("get status=%d body=%s", rec.Code, rec.Body.String())
	}

	// Get unknown -> 404.
	rec = doJSON(t, handler, http.MethodGet, "/api/instructions/9999", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("get unknown status=%d, want 404", rec.Code)
	}

	// Update.
	rec = doJSON(t, handler, http.MethodPut, "/api/instructions/"+strconv.FormatInt(id, 10), `{"name":"Instruction01","description":"d2","content":"# bye"}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("update status=%d body=%s", rec.Code, rec.Body.String())
	}

	// Delete.
	rec = doJSON(t, handler, http.MethodDelete, "/api/instructions/"+strconv.FormatInt(id, 10), "")
	if rec.Code != http.StatusNoContent {
		t.Fatalf("delete status=%d, want 204", rec.Code)
	}
}

func TestInstructionsInstallEndpoints(t *testing.T) {
	handler := newInstructionsServer(t)

	rec := doJSON(t, handler, http.MethodPost, "/api/instructions", `{"name":"WithInstall","content":"x"}`)
	if rec.Code != http.StatusCreated {
		t.Fatalf("create status=%d body=%s", rec.Code, rec.Body.String())
	}
	var created map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &created)
	id := int64(created["id"].(float64))

	// Install user-level to claude.
	rec = doJSON(t, handler, http.MethodPost, "/api/instructions/"+strconv.FormatInt(id, 10)+"/installs", `{"app":"claude","level":"user"}`)
	if rec.Code != http.StatusCreated {
		t.Fatalf("install status=%d body=%s", rec.Code, rec.Body.String())
	}
	var install map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &install); err != nil {
		t.Fatalf("install json: %v", err)
	}
	installID := int64(install["id"].(float64))

	// Project-level without project_dir -> 400.
	rec = doJSON(t, handler, http.MethodPost, "/api/instructions/"+strconv.FormatInt(id, 10)+"/installs", `{"app":"claude","level":"project"}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("project no-dir status=%d, want 400", rec.Code)
	}

	// Copilot user-level is now supported.
	rec = doJSON(t, handler, http.MethodPost, "/api/instructions/"+strconv.FormatInt(id, 10)+"/installs", `{"app":"copilot","level":"user"}`)
	if rec.Code != http.StatusCreated {
		t.Fatalf("copilot user-level status=%d, want 201", rec.Code)
	}

	// Duplicate install at same path now backs up the existing file and succeeds.
	rec = doJSON(t, handler, http.MethodPost, "/api/instructions/"+strconv.FormatInt(id, 10)+"/installs", `{"app":"claude","level":"user"}`)
	if rec.Code != http.StatusCreated {
		t.Fatalf("re-install status=%d, want 201 body=%s", rec.Code, rec.Body.String())
	}

	// Uninstall.
	rec = doJSON(t, handler, http.MethodDelete, "/api/instructions/installs/"+strconv.FormatInt(installID, 10), "")
	if rec.Code != http.StatusNoContent {
		t.Fatalf("uninstall status=%d, want 204", rec.Code)
	}
}

func TestInstructionTargetsEndpoint(t *testing.T) {
	handler := newInstructionsServer(t)
	rec := doJSON(t, handler, http.MethodGet, "/api/instructions/targets", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("targets status=%d body=%s", rec.Code, rec.Body.String())
	}
	var targets []InstructionTarget
	if err := json.Unmarshal(rec.Body.Bytes(), &targets); err != nil {
		t.Fatalf("targets json: %v", err)
	}
	byApp := map[string]map[string]bool{}
	for _, tgt := range targets {
		byApp[tgt.App] = tgt.Supports
	}
	if s, ok := byApp["claude"]; !ok || !s["user"] || !s["project"] {
		t.Fatalf("claude supports = %+v", byApp["claude"])
	}
	if s, ok := byApp["copilot"]; !ok || !s["user"] || !s["project"] {
		t.Fatalf("copilot supports = %+v", byApp["copilot"])
	}
}
