import os
import sublime
import sublime_plugin
import platform
import re
import subprocess
from subprocess import Popen, PIPE

settings = None


class Settings:

    def __init__(self):
        package_settings = sublime.load_settings("RustAutoComplete.sublime-settings")
        package_settings.add_on_change("racer", settings_changed)
        package_settings.add_on_change("search_paths", settings_changed)

        self.racer_bin = package_settings.get("racer", "racer")
        self.search_paths = package_settings.get("search_paths", [])
        self.package_settings = package_settings

    def unload(self):
        self.package_settings.clear_on_change("racer")
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
        self.row = int(parts[1])
        self.column = int(parts[2])
        self.path = parts[3]
        self.type = parts[4]


def expand_all(paths):
    return [os.path.expanduser(path)
            for path in paths]


def run_racer(view, cmd_list):
    # Retrieve the entire buffer
    region = sublime.Region(0, view.size())
    content = view.substr(region)

    # Save that buffer to a temporary file for racer to use
    temp_filename = "current.racertmp"
    current_path = os.path.dirname(view.file_name())
    temp_file_path = os.path.join(current_path, temp_filename)
    with open(temp_file_path, "w") as cache_file:
        cache_file.write(content)
    cmd_list.insert(0, settings.racer_bin)
    cmd_list.append(temp_file_path)

    # Copy the system environment and add the source search
    # paths for racer to it.
    expanded_search_paths = expand_all(settings.search_paths)
    env_path = ":".join(expanded_search_paths)
    env = os.environ.copy()
    env['RUST_SRC_PATH'] = env_path

    # Run racer
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    process = Popen(cmd_list, stdout=PIPE, env=env, startupinfo=startupinfo)
    (output, err) = process.communicate()
    exit_code = process.wait()

#    print(output)

    # Remove temp file
    os.remove(temp_file_path)

    # Parse results
    results = []
    match_string = "MATCH "
    if exit_code == 0:
        for byte_line in output.splitlines():
            line = byte_line.decode("utf-8")
            if line.startswith(match_string):
                parts = line[len(match_string):].split(',', 6)
                result = Result(parts)
                if result.path == view.file_name():
                    continue
                if result.path == temp_file_path:
                    result.path = view.file_name()
                results.append(result)
    else:
        print("failed: exit_code:", exit_code, output)
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
                raw_results = run_racer(view, ["complete", str(row), str(col)])

                results = []
                for result in raw_results:
                    result = "{0}\t{1} ({2})".format(result.completion, result.type,
                                                     os.path.basename(result.path)), result.completion
                    results.append(result)

                if len(results) > 0:
                    # return list(set(results))
                    return (list(set(results)), sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)
            except:
                print("Unable to find racer executable (check settings)")


class RustGotoDefinitionCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        # Get the buffer location in correct format for racer
        row, col = self.view.rowcol(self.view.sel()[0].begin())
        row += 1

        results = run_racer(self.view, ["find-definition", str(row), str(col)])

        if len(results) == 1:
            result = results[0]
            path = result.path
            # On Windows the racer will return the paths without the drive letter and we need the letter for the open_file to work.
            if platform.system() == 'Windows' and not re.compile('^\w\:').match(path): path = 'c:' + path
            encoded_path = "{0}:{1}:{2}".format(result.path, result.row, result.column)
            self.view.window().open_file(encoded_path, sublime.ENCODED_POSITION)
