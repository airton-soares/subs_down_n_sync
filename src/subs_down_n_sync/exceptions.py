"""Exceptions raised by subs_down_n_sync. Message is user-facing (in Portuguese)."""

from __future__ import annotations


class SubsDownError(Exception):
    """Erro base do script — mensagem é o que vai para o usuário."""


class InvalidVideoError(SubsDownError):
    pass


class MissingDependencyError(SubsDownError):
    pass


class MissingCredentialsError(SubsDownError):
    pass


class InvalidLanguageError(SubsDownError):
    pass


class SubtitleNotFoundError(SubsDownError):
    pass


class SubtitleSyncError(SubsDownError):
    pass
