import stat

import pytest


def test_load_credentials_env_vars_priority(monkeypatch, mocker, tmp_path):
    """Env vars têm prioridade absoluta sobre arquivo criptografado."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "envuser")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "envpass")
    mocker.patch("subs_down_n_sync.credentials._CREDS_FILE", tmp_path / "credentials.enc")

    from subs_down_n_sync.credentials import load_credentials

    user, pwd = load_credentials()
    assert user == "envuser"
    assert pwd == "envpass"


def test_save_and_load_credentials_roundtrip(monkeypatch, mocker, tmp_path):
    """Credenciais salvas criptografadas são recuperadas corretamente."""
    monkeypatch.delenv("OPENSUBTITLES_USERNAME", raising=False)
    monkeypatch.delenv("OPENSUBTITLES_PASSWORD", raising=False)
    mocker.patch("subs_down_n_sync.credentials._CONFIG_DIR", tmp_path)
    mocker.patch("subs_down_n_sync.credentials._CREDS_FILE", tmp_path / "credentials.enc")
    mocker.patch("subs_down_n_sync.credentials._get_machine_secret", return_value=b"test-secret")

    from subs_down_n_sync.credentials import load_credentials, save_credentials

    save_credentials("myuser", "mypass")
    user, pwd = load_credentials()
    assert user == "myuser"
    assert pwd == "mypass"


def test_save_credentials_sets_permissions_600(mocker, tmp_path):
    """Arquivo salvo com permissões 0o600."""
    mocker.patch("subs_down_n_sync.credentials._CONFIG_DIR", tmp_path)
    creds_file = tmp_path / "credentials.enc"
    mocker.patch("subs_down_n_sync.credentials._CREDS_FILE", creds_file)
    mocker.patch("subs_down_n_sync.credentials._get_machine_secret", return_value=b"test")

    from subs_down_n_sync.credentials import save_credentials

    save_credentials("u", "p")
    assert stat.S_IMODE(creds_file.stat().st_mode) == 0o600


def test_load_credentials_prompts_when_no_file(monkeypatch, mocker, tmp_path):
    """Sem env vars e sem arquivo → _prompt_and_save chamado."""
    monkeypatch.delenv("OPENSUBTITLES_USERNAME", raising=False)
    monkeypatch.delenv("OPENSUBTITLES_PASSWORD", raising=False)
    mocker.patch("subs_down_n_sync.credentials._CREDS_FILE", tmp_path / "credentials.enc")
    mock_prompt = mocker.patch(
        "subs_down_n_sync.credentials._prompt_and_save",
        return_value=("promptuser", "promptpass"),
    )

    from subs_down_n_sync.credentials import load_credentials

    user, pwd = load_credentials()
    mock_prompt.assert_called_once()
    assert user == "promptuser"
    assert pwd == "promptpass"


def test_load_credentials_prompts_on_decryption_failure(monkeypatch, mocker, tmp_path):
    """Arquivo corrompido → re-prompt automático."""
    monkeypatch.delenv("OPENSUBTITLES_USERNAME", raising=False)
    monkeypatch.delenv("OPENSUBTITLES_PASSWORD", raising=False)
    creds_file = tmp_path / "credentials.enc"
    creds_file.write_bytes(b"dados-invalidos")
    mocker.patch("subs_down_n_sync.credentials._CREDS_FILE", creds_file)
    mocker.patch("subs_down_n_sync.credentials._get_machine_secret", return_value=b"secret")
    mock_prompt = mocker.patch(
        "subs_down_n_sync.credentials._prompt_and_save",
        return_value=("u", "p"),
    )

    from subs_down_n_sync.credentials import load_credentials

    load_credentials()
    mock_prompt.assert_called_once()


def test_prompt_and_save_raises_on_empty_credentials(mocker, tmp_path):
    """_prompt_and_save levanta MissingCredentialsError se usuário ou senha vazia."""
    mocker.patch("subs_down_n_sync.credentials._CONFIG_DIR", tmp_path)
    mocker.patch("subs_down_n_sync.credentials._CREDS_FILE", tmp_path / "credentials.enc")
    mocker.patch("subs_down_n_sync.credentials._get_machine_secret", return_value=b"test")
    mocker.patch("builtins.input", return_value="")
    mocker.patch("subs_down_n_sync.credentials.getpass", return_value="")

    from subs_down_n_sync.credentials import _prompt_and_save
    from subs_down_n_sync.exceptions import MissingCredentialsError

    with pytest.raises(MissingCredentialsError):
        _prompt_and_save()
