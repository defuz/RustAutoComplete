# RustAutoComplete
A binding for Sublime Text to the Rust auto completion tool by Phil Dawes (https://github.com/phildawes/racer).

## Features
* Auto complete (invoked automatically on Rust files).
* Go to definition (default key binding is F2).

![Example](/screenshots/completion_1.png)

![Example](/screenshots/completion_2.png)

## Status
Initial version. Works on the basic projects I have tested on. Partially works on Servo when the search paths are set correctly.

Pull requests for fixes and new features are very welcome.

I have only tested this on Linux (Ubuntu 14.04). It may work on Mac / Windows.

## Requirements

1. Install the Rust syntax highlighting package from Package Control:
https://sublime.wbond.net/packages/Rust
2. Clone and build the auto completion tool racer:
https://github.com/phildawes/racer
3. Install the package through package control (or clone from git if you prefer):
https://sublime.wbond.net/packages/RustAutoComplete
4. Configure the plugin to be able to find the racer executable and
Rust source code. Open menu
`Preferences -> Package settings -> RustAutoComplete -> Settings - User`
and edit the settings file using below as a template:

```
{
  // The full path to the racer binary. If racer is already
  // in your system path, then this default will be fine.
  "racer": "racer",

  // A list of search paths. This should generally just
  // be the path to the rust compiler src/ directory.
  "search_paths": [
    "/home/git/rust-lang/rust/src"
  ]
}
```

5. (Optional) Set autocomplete to trigger on '.' and ':'.
Open `Preferences -> Settings - User` and add this entry:

```
  "auto_complete_triggers": [ {"selector": "source.rust", "characters": ".:"} ],
```

6. (Optional) Set a keybinding for triggering autocomplete (the Linux default is `alt+/`, which isn't common elsewhere).
Open `Preferences -> Key Bindings - User` and add these entries (for a `Ctrl+Space` trigger):

```
    { "keys": ["ctrl+space"], "command": "auto_complete" },
    { "keys": ["ctrl+space"], "command": "replace_completion_with_auto_complete", "context":
        [
            { "key": "last_command", "operator": "equal", "operand": "insert_best_completion" },
            { "key": "auto_complete_visible", "operator": "equal", "operand": false },
            { "key": "setting.tab_completion", "operator": "equal", "operand": true }
        ]
    },
```

## Contact
https://github.com/glennw/RustAutoComplete
