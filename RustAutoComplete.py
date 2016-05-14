import os
import sublime
import sublime_plugin
import re
import subprocess
import tempfile
from subprocess import Popen, PIPE


settings = None


class Settings:
    def __init__(self):
        package_settings = sublime.load_settings("RustAutoComplete.sublime-settings")
        package_settings.add_on_change("racer", settings_changed)
        package_settings.add_on_change("cargo_home", settings_changed)
        package_settings.add_on_change("search_paths", settings_changed)

        self.racer_bin = package_settings.get("racer", "racer")
        self.cargo_home = package_settings.get("cargo_home", os.environ.get("CARGO_HOME", ""))
        self.search_paths = package_settings.get("search_paths", [])
        self.package_settings = package_settings

    def unload(self):
        self.package_settings.clear_on_change("racer")
        self.package_settings.clear_on_change("cargo_home")
        self.package_settings.clear_on_change("search_paths")


def plugin_loaded():
    global settings
    settings = Settings()


def plugin_unloaded():
    global settings
    if settings != None:
        settings.unload()
        settings = None


def settings_changed():
    global settings
    if settings != None:
        settings.unload()
        settings = None
    settings = Settings()


class Result:
    def __init__(self, parts):
        self.completion = parts[0]
        self.snippet = parts[1]
        self.row = int(parts[2])
        self.column = int(parts[3])
        self.path = parts[4]
        self.type = parts[5]
        self.context = parts[6]

def expand_all(paths):
    return [os.path.expanduser(path)
        for path in paths]

def determine_save_dir(view):
    # If we return None then it will fall back on the system tmp directory
    save_dir = None

    # Try to save to the same directory the file is saved in
    if view.file_name() is not None:
        save_dir = os.path.dirname(view.file_name())

    # If the file has not been saved, and the window has a folder open,
    # try to treat the main folder as if it were a cargo project
    source_folder = ""
    if len(view.window().folders()) > 0:
        source_folder = os.path.join(view.window().folders()[0], "src")
    if save_dir is None and os.path.isdir(source_folder):
        save_dir = source_folder

    # If nothing else has worked, look at the folders that other open files are in
    if save_dir is None:
        paths = [v.file_name() for v in view.window().views() if v.file_name() is not None]
        # We only care about open rust files
        paths = [path for path in paths if path[-3:] == ".rs"]
        directories = [os.path.dirname(path) for path in paths]
        if len(directories) == 0:
            return None

        # Count the frequency of occurance of each path
        dirs = {}
        for item in directories:
            if item not in dirs:
                dirs[item] = 1
            else:
                dirs[item] += 1

        # Use the most common path
        save_dir = max(dirs.keys(), key=(lambda key: dirs[key]))

    return save_dir


def run_racer(view, cmd_list):
    # Retrieve the entire buffer
    region = sublime.Region(0, view.size())
    content = view.substr(region)
    with_snippet = cmd_list[0] == "complete-with-snippet"

    # Figure out where to save the temp file so that racer can do
    # autocomplete based on other user files
    save_dir = determine_save_dir(view)

    # Save that buffer to a temporary file for racer to use
    temp_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, dir=save_dir)
    temp_file_path = temp_file.name
    temp_file.write(content)
    temp_file.close()
    cmd_list.insert(0, settings.racer_bin)
    cmd_list.append(temp_file_path)

    # Copy the system environment and add the source search paths and cargo home
    env = os.environ.copy()
    expanded_search_paths = expand_all(settings.search_paths)
    if 'RUST_SRC_PATH' in env:
        expanded_search_paths.append(env['RUST_SRC_PATH'])
    env['RUST_SRC_PATH'] = os.pathsep.join(expanded_search_paths)
    env['CARGO_HOME'] = settings.cargo_home

    # Run racer
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    process = Popen(cmd_list, stdout=PIPE, stderr=PIPE, env=env, startupinfo=startupinfo)
    (output, err) = process.communicate()
    exit_code = process.wait()

    # Remove temp file
    os.remove(temp_file_path)

    # Parse results
    results = []
    match_string = "MATCH "
    if exit_code == 0:
        for byte_line in output.splitlines():
            line = byte_line.decode("utf-8")
            if line.startswith(match_string):
                if with_snippet:
                    parts = line[len(match_string):].split(';', 7)
                else:
                    parts = line[len(match_string):].split(',', 6)
                    parts.insert(1, "")

                result = Result(parts)
                if result.path == view.file_name():
                    continue
                if result.path == temp_file_path:
                    result.path = view.file_name()
                results.append(result)
    else:
        print("CMD: '%s' failed: exit_code:" % ' '.join(cmd_list), exit_code, output, err)
    return results


class RustAutocomplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        # Check if this is a Rust source file. This check
        # relies on the Rust syntax formatting extension
        # being installed - https://github.com/jhasse/sublime-rust
        if view.match_selector(locations[0], "source.rust"):
            # Get the buffer location in correct format for racer
            row, col = view.rowcol(locations[0])
            row += 1

            try:
                raw_results = run_racer(view, ["complete-with-snippet", str(row), str(col)])
            except FileNotFoundError:
                print("Unable to find racer executable (check settings)")
                return

            results = []
            lalign = 0;
            ralign = 0;
            for result in raw_results:
                result.middle = "{0} ({1})".format(result.type, os.path.basename(result.path))
                lalign = max(lalign,len(result.completion)+len(result.middle))
                ralign = max(ralign, len(result.context))

            for result in raw_results:
                context = result.context
                result = "{0} {1:>{3}} : {2:{4}}".format(result.completion, result.middle, result.context, lalign - len(result.completion), ralign), result.snippet
                results.append(result)
            if len(results) > 0:
                # return list(set(results))
                return (list(set(results)),
                        sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)


class RustGotoDefinitionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        # Get the buffer location in correct format for racer
        row, col = self.view.rowcol(self.view.sel()[0].begin())
        row += 1

        results = run_racer(self.view, ["find-definition", str(row), str(col)])

        if len(results) == 1:
            result = results[0]
            path = result.path
            # On Windows the racer will return the paths without the drive
            # letter and we need the letter for the open_file to work.
            if sublime.platform() == 'windows' and not re.compile('^\w\:').match(path):
                path = 'c:' + path
            encoded_path = "{0}:{1}:{2}".format(path, result.row, result.column)
            self.view.window().open_file(encoded_path, sublime.ENCODED_POSITION)
