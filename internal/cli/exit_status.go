package cli

import "fmt"

type exitStatusError struct {
	code int
	err  error
}

func (e *exitStatusError) Error() string {
	if e.err == nil {
		return fmt.Sprintf("exit status %d", e.code)
	}
	return e.err.Error()
}

func (e *exitStatusError) Unwrap() error {
	return e.err
}

func withExitStatus(code int, err error) error {
	return &exitStatusError{code: code, err: err}
}
