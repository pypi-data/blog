import ast

from pkg_check import context_label, file_kind, find_imports


def labels(src):
    return [(m, context_label(c)) for m, _, c in find_imports(ast.parse(src))]


def test_plain_import_is_module_level():
    assert labels("import pkg_resources\n") == [("pkg_resources", "module")]


def test_from_import_counts():
    assert labels("from pkg_resources import get_distribution\n") == [("pkg_resources", "module")]


def test_submodule_import_counts():
    assert labels("from pkg_resources.extern import packaging\n") == [("pkg_resources", "module")]


def test_namespace_package_line_counts():
    src = "__import__('pkg_resources').declare_namespace(__name__)\n"
    assert labels(src) == [("pkg_resources", "module")]


def test_guarded_namespace_package_line():
    src = ("try:\n    __import__('pkg_resources').declare_namespace(__name__)\n"
           "except ImportError:\n    __path__ = __import__('pkgutil').extend_path(__path__, __name__)\n")
    assert labels(src) == [("pkg_resources", "guarded")]


def test_import_module_call_counts():
    assert labels("import importlib\nm = importlib.import_module('pkg_resources')\n") == [("pkg_resources", "module")]


def test_other_dynamic_imports_ignored():
    assert labels("__import__('pkgutil')\nimportlib.import_module(name)\n") == []


def test_try_import_error_is_guarded():
    src = "try:\n    import pkg_resources\nexcept ImportError:\n    pkg_resources = None\n"
    assert labels(src) == [("pkg_resources", "guarded")]


def test_importlib_metadata_first_is_fallback():
    src = ("try:\n    from importlib.metadata import version\nexcept ImportError:\n"
           "    from pkg_resources import get_distribution\n")
    assert labels(src) == [("pkg_resources", "fallback")]


def test_try_with_unrelated_handler_is_not_guarded():
    assert labels("try:\n    import pkg_resources\nexcept KeyError:\n    pass\n") == [("pkg_resources", "module")]


def test_version_check_is_gated():
    src = ("import sys\nif sys.version_info >= (3, 8):\n    from importlib import metadata\n"
           "else:\n    import pkg_resources\n")
    assert labels(src) == [("pkg_resources", "gated")]


def test_import_in_function():
    assert labels("def version():\n    import pkg_resources\n") == [("pkg_resources", "function")]


def test_relative_and_other_imports_ignored():
    assert labels("from . import pkg_resources\nfrom pip._vendor import pkg_resources\nimport pkgutil\n") == []


def test_file_kind():
    assert file_kind("pkg/tests/test_x.py") == "test"
    assert file_kind("setup.py") == "setup"
    assert file_kind("docs/conf.py") == "docs"
    assert file_kind("pkg/__init__.py") == "code"
    assert file_kind("pkg/_tests/utils.py") == "test"
    assert file_kind("pkg/models/llama/benchmark_all.py") == "docs"


def test_form_is_recorded():
    src = "import pkg_resources\nfrom pkg_resources import require\n__import__('pkg_resources')\n"
    assert [c["form"] for _, _, c in find_imports(ast.parse(src))] == ["import", "from", "dynamic"]


def test_sys_modules_check_is_loaded():
    src = "import sys\ndef f():\n    if 'pkg_resources' in sys.modules:\n        import pkg_resources\n"
    assert labels(src) == [("pkg_resources", "loaded")]


def test_find_spec_check_is_loaded():
    src = "import importlib.util\nif importlib.util.find_spec('pkg_resources'):\n    import pkg_resources\n"
    assert labels(src) == [("pkg_resources", "loaded")]


def test_suppress_is_guarded():
    src = ("from contextlib import suppress\ndef f():\n    with suppress(Exception):\n"
           "        from pkg_resources import parse_version\n")
    assert labels(src) == [("pkg_resources", "guarded")]
    assert labels("with suppress(KeyError):\n    import pkg_resources\n") == [("pkg_resources", "module")]


def test_version_alias_is_gated():
    src = "pyver = sys.version_info\nif pyver.major == 3 and pyver.minor <= 9:\n    import pkg_resources\n"
    assert labels(src) == [("pkg_resources", "gated")]
