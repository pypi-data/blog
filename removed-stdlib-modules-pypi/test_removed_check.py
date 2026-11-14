import ast

from removed_check import context_label, file_kind, find_imports


def labels(src):
    return [(m, context_label(c)) for m, _, c in find_imports(ast.parse(src))]


def test_plain_import_is_module_level():
    assert labels("import imp\n") == [("imp", "module")]


def test_from_import_counts_top_level_module():
    assert labels("from distutils.version import LooseVersion\n") == [("distutils", "module")]


def test_try_import_error_is_guarded():
    assert labels("try:\n    import audioop\nexcept ImportError:\n    audioop = None\n") == [("audioop", "guarded")]


def test_try_with_unrelated_handler_is_not_guarded():
    assert labels("try:\n    import cgi\nexcept KeyError:\n    pass\n") == [("cgi", "module")]


def test_import_in_except_is_fallback():
    src = "try:\n    from shlex import quote\nexcept ImportError:\n    from pipes import quote\n"
    assert labels(src) == [("pipes", "fallback")]


def test_version_check_is_gated_in_both_branches():
    src = ("import sys\nif sys.version_info < (3, 12):\n    import imp\nelse:\n    import importlib\n"
           "if sys.version_info >= (3, 12):\n    pass\nelse:\n    import imp\n")
    assert labels(src) == [("imp", "gated"), ("imp", "gated")]


def test_py3k_flag_is_gated():
    assert labels("if py3k:\n    pass\nelse:\n    from imp import new_module\n") == [("imp", "gated")]


def test_other_if_is_not_gated():
    assert labels("if DEBUG:\n    import cgitb\n") == [("cgitb", "module")]


def test_import_in_function():
    assert labels("def f():\n    import telnetlib\n") == [("telnetlib", "function")]


def test_relative_and_other_imports_ignored():
    assert labels("from . import imp\nimport os\nimport impala\n") == []


def test_file_kind():
    assert file_kind("pkg/tests/test_x.py") == "test"
    assert file_kind("test_x.py") == "test"
    assert file_kind("setup.py") == "setup"
    assert file_kind("docs/conf.py") == "docs"
    assert file_kind("pkg/compat.py") == "code"
