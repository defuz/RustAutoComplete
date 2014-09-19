import sys
from unittest import main, TestCase
try:
    from mock import Mock, patch, ANY
except ImportError:
    pass


class SublimeTest(TestCase):

    def setUp(self):
        self.patch_sublime_imports()

    def patch_sublime_imports(self):
        self.sublime = Mock()
        sys.modules["sublime"] = self.sublime
        self.sublime_plugin = Mock()
        sys.modules["sublime_plugin"] = self.sublime_plugin


class RunRacerTests(SublimeTest):

    def setUp(self):
        super(type(self), self).setUp()
        self.set_up_patches()
        self.set_defaults()

    def set_up_patches(self):
        self.popen_patcher = patch("RustAutoComplete.Popen")
        self.popen = self.popen_patcher.start()
        self.os_patcher = patch("RustAutoComplete.os")
        self.os = self.os_patcher.start()
        self.settings_patcher = patch("RustAutoComplete.settings")
        self.settings = self.settings_patcher.start()
        self.print_patcher = patch("RustAutoComplete.print", create=True)
        self.printer = self.print_patcher.start()
        self.open_patcher = patch("RustAutoComplete.open", create=True)
        self.open = self.open_patcher.start()

    def set_defaults(self):
        self.process = Mock()
        self.popen.return_value = self.process
        self.process.communicate.return_value = (b"this\nis\nthe\nstdout", b"this\nis\nthe\nstderr")
        self.process.wait.return_value = 0
        self.os.path.expanduser = lambda path: "expanded({})".format(path)
        self.os.path.dirname = lambda path: path.split("/")[1]
        self.os.path.join = lambda p1, p2: "{0}+{1}".format(p1, p2)
        self.os.environ.copy.return_value = {}
        self.settings.search_paths = ["/path/to/rust/sources", "~/workspace/rust-src", "~/../rust"]
        self.settings.racer_bin = "/bin/racer"

    def tearDown(self):
        super(type(self), self).tearDown()
        self.popen_patcher.stop()
        self.os_patcher.stop()
        self.settings_patcher.stop()
        self.print_patcher.stop()
        self.open_patcher.stop()

    def test_should_set_up_racer_command_line(self):
        view = Mock()
        view.file_name.return_value = "/any-directory/file"

        from RustAutoComplete import run_racer
        run_racer(view, ["any", "racer", "commands"])

        self.popen.assert_called_with(['/bin/racer', 'any', 'racer', 'commands', 'any-directory+current.racertmp'],
                                      startupinfo=ANY,
                                      env=ANY,
                                      stdout=ANY)

    def test_should_expand_all_search_paths(self):
        view = Mock()
        view.file_name.return_value = "/any-directory/file"

        from RustAutoComplete import run_racer
        run_racer(view, ["any", "racer", "commands"])

        self.popen.assert_called_with(ANY,
                                      startupinfo=ANY,
                                      env={
                                          'RUST_SRC_PATH': 'expanded(/path/to/rust/sources):expanded(~/workspace/rust-src):expanded(~/../rust)'},
                                      stdout=ANY)

    def test_should_print_problem_when_exit_code_is_one(self):
        view = Mock()
        view.file_name.return_value = "/any-directory/file"
        self.process.wait.return_value = 1

        from RustAutoComplete import run_racer
        run_racer(view, ["any", "racer", "commands"])

        self.printer.assert_called_with('failed: exit_code:',
                                        1,
                                        b'this\nis\nthe\nstdout')

    def test_should_return_completions_when_exit_code_is_zero(self):
        view = Mock()
        view.file_name.return_value = "/any-directory/file"
        self.process.wait.return_value = 0
        self.process.communicate.return_value = (b"MATCH glob,80,7,/home/hein/git/rust/src/libglob/lib.rs,statement",
                                                 b"this\nis\nthe\nstderr")

        from RustAutoComplete import run_racer
        results = run_racer(view, ["any", "racer", "commands"])

        self.assertEqual(len(results), 1)
        single_result = results[0]
        self.assertEqual(single_result.path, "/home/hein/git/rust/src/libglob/lib.rs")
        self.assertEqual(single_result.column, 7)
        self.assertEqual(single_result.row, 80)
        self.assertEqual(single_result.completion, "glob")
        self.assertEqual(single_result.type, "statement")

    def test_should_not_return_completions_when_output_is_unexpected(self):
        view = Mock()
        view.file_name.return_value = "/any-directory/file"
        self.process.wait.return_value = 0
        self.process.communicate.return_value = (b"This does not start with 'MATCH '",
                                                 b"this\nis\nthe\nstderr")

        from RustAutoComplete import run_racer
        results = run_racer(view, ["any", "racer", "commands"])

        self.assertEqual(results, [])

    def test_should_skip_match_when_it_is_from_the_view_file(self):
        view = Mock()
        view.file_name.return_value = "/any-directory/file"
        self.process.wait.return_value = 0
        self.process.communicate.return_value = (b"MATCH glob,80,7,/any-directory/file,statement",
                                                 b"this\nis\nthe\nstderr")

        from RustAutoComplete import run_racer
        results = run_racer(view, ["any", "racer", "commands"])

        self.assertEqual(results, [])

if __name__ == '__main__':
    main()
