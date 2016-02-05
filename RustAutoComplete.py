import os
import sublime
import sublime_plugin
import re
import subprocess
import tempfile
from subprocess import Popen, PIPE


class Racer:
    def load(self):
        package_settings = sublime.load_settings("RustAutoComplete.sublime-settings")
        package_settings.add_on_change("racer", self.reload)
        package_settings.add_on_change("search_paths", self.reload)

        self.racer_bin = package_settings.get("racer", "racer")
        search_paths = package_settings.get("search_paths", [])
        self.package_settings = package_settings

        # Copy the system environment and add the source search
        # paths for racer to it
        env = os.environ.copy()
        expanded_search_paths = [os.path.expanduser(path) for path in search_paths]
        if 'RUST_SRC_PATH' in env:
            expanded_search_paths.append(env['RUST_SRC_PATH'])
        env['RUST_SRC_PATH'] = os.pathsep.join(expanded_search_paths)

        # Run racer
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.process = Popen([self.racer_bin, "-i", "tab-text", "daemon"],
                             stdin=PIPE, stdout=PIPE, stderr=PIPE,
                             universal_newlines=True, bufsize=0,
                             env=env, startupinfo=startupinfo)

    def unload(self):
        if hasattr(self, 'package_settings'):
            self.package_settings.clear_on_change("racer")
            self.package_settings.clear_on_change("search_paths")
        if hasattr(self, 'process'):
            self.process.kill()

    def reload(self):
        self.unload()
        self.load()

    def run_command(self, args, content):
        self.process.stdin.write('\t'.join(args))
        self.process.stdin.write('\n')
        self.process.stdin.write(content)
        self.process.stdin.write('\x04')

        print("input ", '\t'.join(args), '\n', content)

        returncode = self.process.poll()
        if returncode is not None:
            print("%s is failed with exit code %s and stderr:" % (self.racer_bin, returncode))
            print(self.process.stderr.read())
            sublime.error_message("Racer quit unexpectedly. See console for more info.")
            self.process = None
            self.reload()
            return []

        results = []

        while True:
            line = self.process.stdout.readline()
            parts = line.rstrip().split('\t')
            if parts[0] == 'MATCH':
                if len(parts) == 7: # without snippet
                    parts.insert(2, None)
                results.append(Result(parts))
                continue
            if parts[0] == 'END':
                break

        return results

    def complete_with_snippet(self, row, col, filename, content):
        args = ["complete-with-snippet", str(row), str(col), filename, '-']
        return self.run_command(args, content)

    def find_definition(self, row, col, filename, content):
        args = ["find-definition", str(row), str(col), filename, '-']
        return self.run_command(args, content)


racer = Racer()
plugin_loaded = racer.load
plugin_unloaded = racer.unload


class Result:
    def __init__(self, parts):
        self.completion = parts[1]
        self.snippet = parts[2]
        self.row = int(parts[3])
        self.column = int(parts[4])
        self.path = parts[5]
        self.type = parts[6]
        self.context = parts[7]


class RustAutocomplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        # Check if this is a Rust source file. This check
        # relies on the Rust syntax formatting extension
        # being installed - https://github.com/jhasse/sublime-rust
        if not view.match_selector(locations[0], "source.rust"):
            return None

        row, col = view.rowcol(locations[0])
        region = sublime.Region(0, view.size())
        content = view.substr(region)
        raw_results = racer.complete_with_snippet(row+1, col, view.file_name(), content)

        results = []
        lalign = 0
        ralign = 0
        for result in raw_results:
            result.middle = "{0} ({1})".format(result.type, os.path.basename(result.path))
            lalign = max(lalign, len(result.completion)+len(result.middle))
            ralign = max(ralign, len(result.context))

        for result in raw_results:
            context = result.context
            result = "{0} {1:>{3}} : {2:{4}}".format(result.completion, result.middle, result.context, lalign - len(result.completion), ralign), result.snippet
            results.append(result)
        if results:
            return (list(results),
                    sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)


class RustGotoDefinitionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        row, col = self.view.rowcol(self.view.sel()[0].begin())
        region = sublime.Region(0, self.view.size())
        content = self.view.substr(region)
        results = racer.find_definition(row+1, col, self.view.file_name(), content)
        if len(results) == 1:
            result = results[0]
            path = result.path
            # On Windows the racer will return the paths without the drive
            # letter and we need the letter for the open_file to work.
            if sublime.platform() == 'windows' and not re.compile('^\w\:').match(path):
                path = 'c:' + path
            encoded_path = "{0}:{1}:{2}".format(path, result.row, result.column+1)
            self.view.window().open_file(encoded_path, sublime.ENCODED_POSITION)
