# Visual Demo: Dynamic Filtering in Action

## Scenario: Selecting from 40+ AI Models

### Step 1: Initial Display (All Items)
```
╔════════════════════════════════════════════════╗
║      Choose AI Model:                          ║
╠════════════════════════════════════════════════╣
║ Filter: (type to filter)                       ║
╠════════════════════════════════════════════════╣
║  1) gpt-4.1                                    ║
║  2) gpt-5-mini                                 ║
║  3) gpt-5                                      ║
║  4) gpt-3.5-turbo                              ║
║  5) gpt-3.5-turbo-0613                         ║
║  6) gpt-4o-mini                                ║
║  7) gpt-4o-mini-2024-07-18                     ║
║  ...                                           ║
║ 39) gpt-4.1-2025-04-14                         ║
║ 40) Cancel                                     ║
╚════════════════════════════════════════════════╝

Use ↑/↓ to navigate, type to filter, Enter to select
```

### Step 2: User Types "gpt" (Filter Applied)
```
╔════════════════════════════════════════════════╗
║      Choose AI Model:                          ║
╠════════════════════════════════════════════════╣
║ Filter: gpt                                    ║
╠════════════════════════════════════════════════╣
║  1) gpt-4.1                                    ║
║  2) gpt-5-mini                                 ║
║  3) gpt-5                                      ║
║  4) gpt-3.5-turbo                              ║
║  5) gpt-3.5-turbo-0613                         ║
║  6) gpt-4o-mini                                ║
║  7) gpt-4o-mini-2024-07-18                     ║
║  8) gpt-4                                      ║
║  9) gpt-4-0613                                 ║
║ 10) gpt-4-0125-preview                         ║
║ 11) gpt-4o                                     ║
║ 12) gpt-4o-2024-11-20                          ║
║ 13) gpt-4o-2024-05-13                          ║
║ 14) gpt-4-o-preview                            ║
║ 15) gpt-4o-2024-08-06                          ║
║ 16) gpt-11-copilot                             ║
║ 17) gpt-5-codex                                ║
║ 18) gpt-4.1-2025-04-14                         ║
║ 19) Cancel                                     ║
╚════════════════════════════════════════════════╝

Use ↑/↓ to navigate, type to filter, Enter to select
```

**Result**: 40 items → 18 GPT models (55% reduction!)

### Step 3: User Continues Typing "4" (Further Refined)
```
╔════════════════════════════════════════════════╗
║      Choose AI Model:                          ║
╠════════════════════════════════════════════════╣
║ Filter: gpt4                                   ║
╠════════════════════════════════════════════════╣
║  1) gpt-4.1                                    ║
║  2) gpt-4o-mini                                ║
║  3) gpt-4o-mini-2024-07-18                     ║
║  4) gpt-4                                      ║
║  5) gpt-4-0613                                 ║
║  6) gpt-4-0125-preview                         ║
║  7) gpt-4o                                     ║
║  8) gpt-4o-2024-11-20                          ║
║  9) gpt-4o-2024-05-13                          ║
║ 10) gpt-4-o-preview                            ║
║ 11) gpt-4o-2024-08-06                          ║
║ 12) gpt-4.1-2025-04-14                         ║
║ 13) Cancel                                     ║
╚════════════════════════════════════════════════╝

Use ↑/↓ to navigate, type to filter, Enter to select
```

**Result**: 18 items → 12 GPT-4 models (70% reduction from original!)

### Step 4: User Types "o" (Final Refinement)
```
╔════════════════════════════════════════════════╗
║      Choose AI Model:                          ║
╠════════════════════════════════════════════════╣
║ Filter: gpt4o                                  ║
╠════════════════════════════════════════════════╣
║  1) gpt-4o-mini                                ║
║  2) gpt-4o-mini-2024-07-18                     ║
║  3) gpt-4o                                     ║
║  4) gpt-4o-2024-11-20                          ║
║  5) gpt-4o-2024-05-13                          ║
║  6) gpt-4-o-preview                            ║
║  7) gpt-4o-2024-08-06                          ║
║  8) Cancel                                     ║
╚════════════════════════════════════════════════╝

Use ↑/↓ to navigate, type to filter, Enter to select
```

**Result**: 40 items → 7 GPT-4o models (82.5% reduction!)

### Step 5: User Presses Enter (Selection Made)
```
✓ Selected: gpt-4o-mini
```

---

## Alternative Workflow: Clearing Filter

### User Changes Mind
```
╔════════════════════════════════════════════════╗
║      Choose AI Model:                          ║
╠════════════════════════════════════════════════╣
║ Filter: gpt4o                                  ║
╠════════════════════════════════════════════════╣
║  1) gpt-4o-mini                                ║
...
╚════════════════════════════════════════════════╝
```

**User presses Esc**

```
╔════════════════════════════════════════════════╗
║      Choose AI Model:                          ║
╠════════════════════════════════════════════════╣
║ Filter: (type to filter)                       ║
╠════════════════════════════════════════════════╣
║  1) gpt-4.1                                    ║
║  2) gpt-5-mini                                 ║
...
║ 40) Cancel                                     ║
╚════════════════════════════════════════════════╝
```

**User types "claude"**

```
╔════════════════════════════════════════════════╗
║      Choose AI Model:                          ║
╠════════════════════════════════════════════════╣
║ Filter: claude                                 ║
╠════════════════════════════════════════════════╣
║  1) claude-3.5-sonnet                          ║
║  2) claude-3.7-sonnet                          ║
║  3) claude-3.7-sonnet-thought                  ║
║  4) claude-sonnet-4                            ║
║  5) claude-opus-4                              ║
║  6) claude-sonnet-4.5                          ║
║  7) claude-opus-41                             ║
║  8) claude-haiku-4.5                           ║
║  9) Cancel                                     ║
╚════════════════════════════════════════════════╝
```

---

## Time Comparison

### Without Filtering
1. Read through all 40 items
2. Find the one you want
3. Count to find its number
4. Type the number
5. Press Enter

**Total Time**: ~20-30 seconds

### With Filtering
1. Type "gpt4o" (5 keystrokes)
2. See 7 items
3. Press Enter

**Total Time**: ~3-5 seconds

### Speed Improvement: **6-10x faster!** 🚀

---

## Edge Cases Handled

### No Matches
```
╔════════════════════════════════════════════════╗
║      Choose AI Model:                          ║
╠════════════════════════════════════════════════╣
║ Filter: xyz123                                 ║
╠════════════════════════════════════════════════╣
║             No matching items                  ║
║  1) Cancel                                     ║
╚════════════════════════════════════════════════╝
```

**User presses Backspace or Esc to try again**

### Single Match
```
╔════════════════════════════════════════════════╗
║      Choose AI Model:                          ║
╠════════════════════════════════════════════════╣
║ Filter: gemini-2.5-pro                         ║
╠════════════════════════════════════════════════╣
║  1) gemini-2.5-pro                             ║
║  2) Cancel                                     ║
╚════════════════════════════════════════════════╝
```

**Perfect match - just press Enter!**

---

## Real-World Example: Common Use Cases

### Finding Mini Models
Filter: `mini`
```
gpt-5-mini
gpt-4o-mini
gpt-4o-mini-2024-07-18
o3-mini
o3-mini-2025-01-31
o3-mini-paygo
o4-mini
o4-mini-2025-04-16
```

### Finding 2024 Models
Filter: `2024`
```
gpt-4o-mini-2024-07-18
gpt-4o-2024-11-20
gpt-4o-2024-05-13
gpt-4o-2024-08-06
```

### Finding Sonnet Models
Filter: `sonnet`
```
claude-3.5-sonnet
claude-3.7-sonnet
claude-3.7-sonnet-thought
claude-sonnet-4
claude-sonnet-4.5
```

---

## Summary: Before vs After

| Aspect | Before | After |
|--------|--------|-------|
| **Items visible** | All 40 | Filtered subset |
| **Selection time** | 20-30 sec | 3-5 sec |
| **User action** | Scroll, count, type number | Type filter, press Enter |
| **Cognitive load** | High (read all items) | Low (see only relevant) |
| **Error rate** | Higher (wrong number) | Lower (visual selection) |
| **User satisfaction** | 😐 Acceptable | 😊 Excellent |

**The difference is dramatic!** 🎉
