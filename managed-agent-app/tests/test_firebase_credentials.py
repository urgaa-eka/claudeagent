"""
Unit tests for the service-account key resolver -- the search order, the
case-insensitive matching that the original hardcoded list got wrong on Android,
and the guarantee that describe_key() never hands back the private key.

Pure filesystem work against tmp_path; no network and no SDK import, so these
always run rather than skipping.
"""

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(relpath, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fc = _load("bridge/firebase_credentials.py", "firebase_credentials")


def _write_key(path, project_id="eka-prod", type_="service_account"):
    """Write a structurally valid (but fake) service-account key."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": type_,
                "project_id": project_id,
                "private_key_id": "deadbeef",
                "private_key": "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n",
                "client_email": f"sdk@{project_id}.iam.gserviceaccount.com",
                "client_id": "12345",
            }
        )
    )
    return path


@pytest.fixture
def empty_cwd(tmp_path, monkeypatch):
    """Run with a clean cwd so the implicit Path.cwd() candidate never matches."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


def test_explicit_path_wins_over_env(tmp_path, empty_cwd):
    explicit = _write_key(tmp_path / "explicit.json")
    other = _write_key(tmp_path / "from-env.json")
    got = fc.resolve_service_account_key(
        explicit=explicit, env={"EKA_SERVICE_ACCOUNT_KEY": str(other)}, home=tmp_path
    )
    assert got == explicit


def test_missing_explicit_path_raises_instead_of_using_another_key(tmp_path, empty_cwd):
    """A typo'd --key must not silently authenticate against a different project."""
    fallback = _write_key(tmp_path / "eka-runner" / "serviceAccountKey.json")
    with pytest.raises(fc.CredentialsNotFound, match="explicitly requested path"):
        fc.resolve_service_account_key(
            explicit=tmp_path / "typo.json", env={}, home=tmp_path
        )
    # The fallback key exists and would have been found by a plain search.
    assert fc.resolve_service_account_key(env={}, home=tmp_path) == fallback


def test_missing_explicit_path_with_require_false_returns_none(tmp_path, empty_cwd):
    _write_key(tmp_path / "eka-runner" / "serviceAccountKey.json")
    got = fc.resolve_service_account_key(
        explicit=tmp_path / "typo.json", env={}, home=tmp_path, require=False
    )
    assert got is None


def test_candidate_list_uses_canonical_filename_casing(tmp_path):
    """The not-found error prints this list; lowercased names read as a demand."""
    paths = fc.candidate_paths(env={}, home=tmp_path)
    assert any(p.name == "serviceAccountKey.json" for p in paths)
    assert not any(p.name == "serviceaccountkey.json" for p in paths)


def test_eka_env_var_wins_over_google_default(tmp_path, empty_cwd):
    eka = _write_key(tmp_path / "eka.json")
    google = _write_key(tmp_path / "google.json")
    got = fc.resolve_service_account_key(
        env={
            "EKA_SERVICE_ACCOUNT_KEY": str(eka),
            "GOOGLE_APPLICATION_CREDENTIALS": str(google),
        },
        home=tmp_path,
    )
    assert got == eka


def test_falls_back_to_google_application_credentials(tmp_path, empty_cwd):
    google = _write_key(tmp_path / "google.json")
    got = fc.resolve_service_account_key(
        env={"GOOGLE_APPLICATION_CREDENTIALS": str(google)}, home=tmp_path
    )
    assert got == google


def test_home_eka_runner_directory_is_searched(tmp_path, empty_cwd):
    key = _write_key(tmp_path / "eka-runner" / "serviceAccountKey.json")
    assert fc.resolve_service_account_key(env={}, home=tmp_path) == key


def test_lowercase_k_spelling_is_found(tmp_path, empty_cwd):
    """The bug the original list shipped: serviceAccountkey.json on a
    case-sensitive filesystem (Android) never matched serviceAccountKey.json."""
    key = _write_key(tmp_path / "eka-runner" / "serviceAccountkey.json")
    assert fc.resolve_service_account_key(env={}, home=tmp_path) == key


def test_console_download_name_is_found(tmp_path, empty_cwd):
    """A key saved straight from the Firebase console, never renamed."""
    key = _write_key(tmp_path / "eka-runner" / "eka-prod-firebase-adminsdk-a1b2-c3d4.json")
    assert fc.resolve_service_account_key(env={}, home=tmp_path) == key


def test_script_dir_is_searched(tmp_path, empty_cwd):
    script_dir = tmp_path / "daemon"
    key = _write_key(script_dir / "serviceAccountKey.json")
    got = fc.resolve_service_account_key(
        env={}, script_dir=script_dir, home=tmp_path / "nonexistent-home"
    )
    assert got == key


def test_exact_name_preferred_over_console_glob(tmp_path, empty_cwd):
    d = tmp_path / "eka-runner"
    _write_key(d / "eka-prod-firebase-adminsdk-a1b2-c3d4.json")
    exact = _write_key(d / "serviceAccountKey.json")
    assert fc.resolve_service_account_key(env={}, home=tmp_path) == exact


def test_missing_key_raises_with_guidance(tmp_path, empty_cwd):
    with pytest.raises(fc.CredentialsNotFound) as exc:
        fc.resolve_service_account_key(env={}, home=tmp_path)
    message = str(exc.value)
    assert "EKA_SERVICE_ACCOUNT_KEY" in message
    assert "Generate new private key" in message


def test_require_false_returns_none(tmp_path, empty_cwd):
    assert fc.resolve_service_account_key(env={}, home=tmp_path, require=False) is None


def test_candidate_paths_are_deduped_and_ordered(tmp_path):
    paths = fc.candidate_paths(
        explicit=tmp_path / "a.json",
        env={"EKA_SERVICE_ACCOUNT_KEY": str(tmp_path / "b.json")},
        home=tmp_path,
    )
    assert paths[0] == tmp_path / "a.json"
    assert paths[1] == tmp_path / "b.json"
    assert len(paths) == len(set(str(p) for p in paths))


def test_describe_key_omits_the_secret(tmp_path):
    key = _write_key(tmp_path / "serviceAccountKey.json", project_id="eka-prod")
    info = fc.describe_key(key)
    assert info["project_id"] == "eka-prod"
    assert info["client_email"] == "sdk@eka-prod.iam.gserviceaccount.com"
    assert info["private_key_present"] is True
    # The whole point: no secret material anywhere in the summary.
    assert "private_key" not in info
    assert "private_key_id" not in info
    assert "FAKE" not in json.dumps(info)
    assert "deadbeef" not in json.dumps(info)


def test_describe_key_rejects_client_config(tmp_path):
    path = tmp_path / "client.json"
    path.write_text(json.dumps({"type": "authorized_user", "client_id": "x"}))
    with pytest.raises(ValueError, match="expected 'service_account'"):
        fc.describe_key(path)


def test_describe_key_rejects_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        fc.describe_key(path)


def test_describe_key_requires_private_key(tmp_path):
    path = tmp_path / "stub.json"
    path.write_text(json.dumps({"type": "service_account", "project_id": "p"}))
    with pytest.raises(ValueError, match="no private_key"):
        fc.describe_key(path)
