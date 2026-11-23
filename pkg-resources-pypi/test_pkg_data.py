from pkg_data import classify, keeps_pkg_resources, repo_url


PATHS = {"code": "pkg/x.py", "test": "pkg/tests/test_x.py", "setup": "setup.py", "docs": "docs/conf.py"}


def hit(context, kind="code", form="import"):
    return {"path": PATHS[kind], "line": 1, "context": context, "kind": kind, "form": form}


def test_pin_below_82():
    assert keeps_pkg_resources(["setuptools<82"])
    assert keeps_pkg_resources(["setuptools>=40,<81"])
    assert keeps_pkg_resources(["setuptools==80.9.0"])


def test_backport_counts():
    assert keeps_pkg_resources(["pkg-resources-backport>=1.0"])
    assert keeps_pkg_resources(["pkg_resources_backport"])
    assert not keeps_pkg_resources(["pkg-resources-backport; extra == 'old'"])


def test_no_pin():
    assert not keeps_pkg_resources(["setuptools"])
    assert not keeps_pkg_resources(["setuptools>=61"])
    assert not keeps_pkg_resources(["setuptools<90"])
    assert not keeps_pkg_resources(["setuptools<82; extra == 'legacy'"])
    assert not keeps_pkg_resources(["requests<82"])


def test_worst_context_wins():
    assert classify({"hits": [hit("guarded"), hit("function"), hit("module")]})[0] == "module"
    assert classify({"hits": [hit("guarded"), hit("function")]})[0] == "function"
    assert classify({"hits": [hit("fallback"), hit("loaded")]})[0] == "safe"


def test_tests_and_setup_are_not_code():
    assert classify({"hits": [hit("module", kind="test")]})[0] == "other"
    assert classify({"hits": [hit("module", kind="setup"), hit("module", kind="docs")]})[0] == "setup"
    assert classify({"hits": []})[0] == "other"


def test_pinned_project_is_not_unguarded():
    assert classify({"hits": [hit("module")], "requires_dist": ["setuptools<82"]})[0] == "pinned"


def test_repo_url_prefers_source():
    urls = {"Homepage": "https://example.org", "Source": "https://github.com/a/b/", "Home-page": ""}
    assert repo_url(urls) == "https://github.com/a/b"
    assert repo_url({"Docs": "https://gitlab.com/x/y"}) == "https://gitlab.com/x/y"
    assert repo_url({"Homepage": "https://example.org"}) == ""


def test_vendored_copy_is_its_own_level():
    v = {"path": "nuitka/build/inline_copy/jinja2/loaders.py", "line": 1, "context": "function",
         "kind": "code", "form": "import"}
    assert classify({"hits": [v]})[0] == "vendored"
    assert classify({"hits": [v, hit("module")]})[0] == "module"
    assert classify({"hits": [dict(v, context="guarded")]})[0] == "safe"


def test_more_vendored_dirs():
    for path in ("py/_vendored_packages/apipkg/__init__.py", "node_modules/npm/gyp/pylib/gyp/__init__.py"):
        assert classify({"hits": [dict(hit("function"), path=path)]})[0] == "vendored"
