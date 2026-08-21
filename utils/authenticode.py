"""Central Authenticode trust policy for direct-download Windows artifacts.

``public-trusted`` means Windows built a valid public trust chain and the
signature also has the expected code-signing EKU and a timestamp.

``legacy-integrity-bridge`` is deliberately weaker.  It exists so older
artifacts and one explicitly baked transition release can use the historical
self-issued certificate.  The bridge proves the pinned signer and integrity;
it must never be presented as public certificate trust.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable, Mapping, Sequence


CODE_SIGNING_EKU_OID = "1.3.6.1.5.5.7.3.3"
LEGACY_PIN_COMPATIBILITY_VERSION = "1.5.64"
LEGACY_INTEGRITY_BRIDGE_THUMBPRINTS = frozenset(
    {"4FE575D5119B0FC5DAFB6C1684B2968D340EE8F0"}
)
# v1.5.78 is the one approved direct-download transition release while a
# publicly trusted code-signing identity is being provisioned. No other future
# version inherits this exception. Runtime environment variables remain
# additive/test overrides; trust must not depend on CI-only environment state.
TRANSITION_BRIDGE_VERSION = "1.5.78"
PUBLIC_RELEASE_SIGNER_THUMBPRINTS: frozenset[str] = frozenset()
TRANSITION_BRIDGE_VERSION_ENV = "SSMAKER_TRANSITION_BRIDGE_VERSION"


class AuthenticodeTrust(str, Enum):
    """The only trust outcomes exposed by the update signing policy."""

    PUBLIC_TRUSTED = "public-trusted"
    LEGACY_INTEGRITY_BRIDGE = "legacy-integrity-bridge"
    INVALID = "invalid"


@dataclass(frozen=True)
class AuthenticodeVerification:
    """Normalized Authenticode evidence and its policy classification."""

    trust: AuthenticodeTrust
    reason: str
    status: str = ""
    status_message: str = ""
    thumbprint: str = ""
    subject: str = ""
    issuer: str = ""
    eku_oids: tuple[str, ...] = ()
    timestamp_present: bool = False
    timestamp_subject: str = ""

    @property
    def accepted_for_update(self) -> bool:
        """Whether an updater may execute the artifact."""

        return self.trust in {
            AuthenticodeTrust.PUBLIC_TRUSTED,
            AuthenticodeTrust.LEGACY_INTEGRITY_BRIDGE,
        }

    @property
    def public_trusted(self) -> bool:
        """Whether this is genuine public PKI trust (never the legacy bridge)."""

        return self.trust is AuthenticodeTrust.PUBLIC_TRUSTED


def normalize_thumbprint(value: object) -> str:
    """Return a certificate thumbprint in its comparison form."""

    return "".join(str(value or "").split()).upper()


def parse_thumbprints(values: str | Iterable[object] | None) -> frozenset[str]:
    """Normalize a comma-delimited string or iterable of thumbprints."""

    if values is None:
        return frozenset()
    if isinstance(values, str):
        raw_values: Iterable[object] = values.split(",")
    else:
        raw_values = values
    return frozenset(
        normalized
        for normalized in (normalize_thumbprint(value) for value in raw_values)
        if normalized
    )


def configured_transition_bridge_version() -> str:
    """Return the explicitly approved transition version, or an empty string.

    No transition release is authorized by default.  In particular, this code
    does not implicitly authorize v1.5.65 merely because it follows v1.5.64.
    """

    override = str(os.getenv(TRANSITION_BRIDGE_VERSION_ENV, "") or "").strip().lstrip("vV")
    return override or TRANSITION_BRIDGE_VERSION


def expected_public_signer_thumbprints(
    additional_thumbprints: str | Iterable[object] | None = None,
) -> frozenset[str]:
    """Return baked public signer pins plus optional deployment/test additions."""

    return frozenset(PUBLIC_RELEASE_SIGNER_THUMBPRINTS) | parse_thumbprints(
        additional_thumbprints
    )


def validate_build_signing_configuration(
    signing_mode: str,
    artifact_version: str,
    signing_thumbprint: str,
) -> tuple[bool, str]:
    """Validate that a build can safely use the requested signing identity.

    Build authorization intentionally consults only baked source values. An
    environment override can help runtime tests, but cannot authorize a release.
    """

    mode = str(signing_mode or "").strip().lower()
    version = str(artifact_version or "").strip().lstrip("vV")
    thumbprint = normalize_thumbprint(signing_thumbprint)
    baked_public_signers = parse_thumbprints(PUBLIC_RELEASE_SIGNER_THUMBPRINTS)

    if not thumbprint:
        return False, "build signing thumbprint is empty"
    if mode == "public":
        if not baked_public_signers:
            return False, "baked public release signer allowlist is empty"
        if thumbprint not in baked_public_signers:
            return False, "build signer is not in the baked public release signer allowlist"
        if thumbprint in LEGACY_INTEGRITY_BRIDGE_THUMBPRINTS:
            return False, "historical integrity-bridge signer is never a public release signer"
        return True, "public build signer matches the baked public release signer allowlist"

    if mode != "integrity-bridge":
        return False, f"unsupported signing mode: {mode or 'empty'}"
    if thumbprint not in LEGACY_INTEGRITY_BRIDGE_THUMBPRINTS:
        return False, "integrity-bridge build must use the historical pinned signer"
    if version == LEGACY_PIN_COMPATIBILITY_VERSION:
        return True, "historical v1.5.64 compatibility candidate (nonpublished only)"
    if not TRANSITION_BRIDGE_VERSION:
        return False, "baked transition bridge version is empty"
    if version != TRANSITION_BRIDGE_VERSION:
        return False, "candidate version does not match the baked transition bridge version"
    return True, "explicit transition bridge version and historical signer pin are baked"


def is_legacy_bridge_version(
    artifact_version: str | None,
    *,
    transition_bridge_version: str | None = None,
) -> bool:
    """Return whether a version is an exact, explicitly permitted bridge target."""

    normalized_version = str(artifact_version or "").strip().lstrip("vV")
    normalized_transition = str(transition_bridge_version or "").strip().lstrip("vV")
    return normalized_version == LEGACY_PIN_COMPATIBILITY_VERSION or (
        bool(normalized_transition) and normalized_version == normalized_transition
    )


def _normalize_string_sequence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        candidates: Sequence[object] = (value,)
    elif isinstance(value, Sequence):
        candidates = value
    else:
        candidates = (value,)
    return tuple(str(item).strip() for item in candidates if str(item).strip())


def classify_authenticode(
    evidence: Mapping[str, object],
    *,
    expected_thumbprints: str | Iterable[object] | None = None,
    artifact_version: str | None = None,
    allow_legacy_integrity_bridge: bool = False,
    transition_bridge_version: str | None = None,
) -> AuthenticodeVerification:
    """Classify normalized PowerShell evidence under the central trust policy."""

    status = str(evidence.get("Status") or "").strip()
    status_message = str(evidence.get("StatusMessage") or "").strip()
    thumbprint = normalize_thumbprint(evidence.get("Thumbprint"))
    subject = str(evidence.get("Subject") or "").strip()
    issuer = str(evidence.get("Issuer") or "").strip()
    eku_oids = _normalize_string_sequence(evidence.get("EnhancedKeyUsageOids"))
    timestamp_present = bool(evidence.get("TimestampPresent"))
    timestamp_subject = str(evidence.get("TimestampSubject") or "").strip()

    def result(trust: AuthenticodeTrust, reason: str) -> AuthenticodeVerification:
        return AuthenticodeVerification(
            trust=trust,
            reason=reason,
            status=status,
            status_message=status_message,
            thumbprint=thumbprint,
            subject=subject,
            issuer=issuer,
            eku_oids=eku_oids,
            timestamp_present=timestamp_present,
            timestamp_subject=timestamp_subject,
        )

    if not thumbprint:
        return result(AuthenticodeTrust.INVALID, "invalid: missing signer thumbprint")

    normalized_version = str(artifact_version or "").strip().lstrip("vV")
    normalized_transition_version = str(transition_bridge_version or "").strip().lstrip("vV")
    is_legacy_signer = thumbprint in LEGACY_INTEGRITY_BRIDGE_THUMBPRINTS
    if is_legacy_signer:
        bridge_version_allowed = allow_legacy_integrity_bridge and is_legacy_bridge_version(
            normalized_version,
            transition_bridge_version=normalized_transition_version,
        )
        if bridge_version_allowed and status.lower() in {"valid", "unknownerror"}:
            bridge_label = (
                "historical v1.5.64 updater compatibility"
                if normalized_version == LEGACY_PIN_COMPATIBILITY_VERSION
                else f"explicit transition version {normalized_version}"
            )
            return result(
                AuthenticodeTrust.LEGACY_INTEGRITY_BRIDGE,
                f"legacy-integrity-bridge: {bridge_label}; not public trust",
            )
        if bridge_version_allowed:
            detail = status_message or "no status detail"
            return result(
                AuthenticodeTrust.INVALID,
                f"invalid: legacy signature status {status or 'unknown'} ({detail})",
            )
        return result(
            AuthenticodeTrust.INVALID,
            "invalid: legacy signer is limited to historical v1.5.64 compatibility "
            "or an explicitly configured transition bridge version",
        )

    expected = parse_thumbprints(expected_thumbprints)
    if not expected:
        return result(AuthenticodeTrust.INVALID, "invalid: expected public signer allowlist is empty")
    if thumbprint not in expected:
        return result(AuthenticodeTrust.INVALID, "invalid: signer thumbprint not expected")

    if status.lower() != "valid":
        detail = status_message or "no status detail"
        return result(
            AuthenticodeTrust.INVALID,
            f"invalid: Authenticode status {status or 'unknown'} ({detail})",
        )

    if not subject or not issuer:
        return result(AuthenticodeTrust.INVALID, "invalid: signer subject or issuer is missing")
    if subject.casefold() == issuer.casefold():
        return result(AuthenticodeTrust.INVALID, "invalid: self-issued signer is not public trust")

    if CODE_SIGNING_EKU_OID not in eku_oids:
        return result(AuthenticodeTrust.INVALID, "invalid: code-signing EKU is missing")

    if not timestamp_present:
        return result(AuthenticodeTrust.INVALID, "invalid: trusted timestamp is missing")

    return result(
        AuthenticodeTrust.PUBLIC_TRUSTED,
        "public-trusted: valid Authenticode chain, code-signing EKU, and timestamp",
    )


def _powershell_evidence_script(file_path: str) -> str:
    escaped_path = file_path.replace("'", "''")
    return (
        "$ErrorActionPreference='Stop'; "
        "Import-Module Microsoft.PowerShell.Security -ErrorAction Stop; "
        f"$sig=Get-AuthenticodeSignature -LiteralPath '{escaped_path}'; "
        "if ($null -eq $sig) { Write-Output '{}'; exit 0 }; "
        "$thumb=''; $subject=''; $issuer=''; $eku=@(); "
        "if ($sig.SignerCertificate) { "
        "$thumb=[string]$sig.SignerCertificate.Thumbprint; "
        "$subject=[string]$sig.SignerCertificate.Subject; "
        "$issuer=[string]$sig.SignerCertificate.Issuer; "
        "$eku=@($sig.SignerCertificate.EnhancedKeyUsageList | "
        "ForEach-Object { [string]$_.ObjectId }) }; "
        "$timestampPresent=($null -ne $sig.TimeStamperCertificate); "
        "$timestampSubject=''; if ($timestampPresent) { "
        "$timestampSubject=[string]$sig.TimeStamperCertificate.Subject }; "
        "[PSCustomObject]@{Status=[string]$sig.Status; "
        "StatusMessage=[string]$sig.StatusMessage; Thumbprint=$thumb; "
        "Subject=$subject; Issuer=$issuer; EnhancedKeyUsageOids=@($eku); "
        "TimestampPresent=[bool]$timestampPresent; "
        "TimestampSubject=$timestampSubject} | ConvertTo-Json -Compress"
    )


def verify_authenticode(
    file_path: str | os.PathLike[str],
    *,
    expected_thumbprints: str | Iterable[object] | None = None,
    artifact_version: str | None = None,
    allow_legacy_integrity_bridge: bool = False,
    transition_bridge_version: str | None = None,
    timeout: int = 20,
) -> AuthenticodeVerification:
    """Inspect a Windows file and classify it under the central trust policy."""

    path = Path(file_path) if file_path else None
    if path is None or not path.is_file():
        return AuthenticodeVerification(
            AuthenticodeTrust.INVALID,
            "invalid: file not found",
        )
    if sys.platform != "win32":
        return AuthenticodeVerification(
            AuthenticodeTrust.INVALID,
            "invalid: Authenticode verification is available only on Windows",
        )

    windows_root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    powershell = windows_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    powershell_command = str(powershell) if powershell.is_file() else "powershell.exe"
    powershell_env = os.environ.copy()
    # PowerShell 7 prepends its own module directories when it launches the
    # desktop app. Passing those paths into Windows PowerShell 5 can make the
    # built-in Security module fail with duplicate TypeData errors. Restrict
    # this security subprocess to the standard Windows PowerShell locations.
    module_paths = [
        Path(os.environ.get("ProgramFiles") or r"C:\Program Files") / "WindowsPowerShell" / "Modules",
        windows_root / "System32" / "WindowsPowerShell" / "v1.0" / "Modules",
    ]
    powershell_env["PSModulePath"] = ";".join(str(path) for path in module_paths)

    try:
        proc = subprocess.run(
            [
                powershell_command,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _powershell_evidence_script(str(path)),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=powershell_env,
        )
    except Exception as exc:
        return AuthenticodeVerification(
            AuthenticodeTrust.INVALID,
            f"invalid: signature check invocation failed: {exc}",
        )

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:180]
        return AuthenticodeVerification(
            AuthenticodeTrust.INVALID,
            f"invalid: PowerShell signature check failed: {detail or proc.returncode}",
        )

    try:
        evidence = json.loads((proc.stdout or "").strip() or "{}")
    except (TypeError, json.JSONDecodeError):
        return AuthenticodeVerification(
            AuthenticodeTrust.INVALID,
            "invalid: malformed signature verification output",
        )
    if not isinstance(evidence, Mapping):
        return AuthenticodeVerification(
            AuthenticodeTrust.INVALID,
            "invalid: malformed signature verification output",
        )

    return classify_authenticode(
        evidence,
        expected_thumbprints=expected_thumbprints,
        artifact_version=artifact_version,
        allow_legacy_integrity_bridge=allow_legacy_integrity_bridge,
        transition_bridge_version=transition_bridge_version,
    )


__all__ = [
    "AuthenticodeTrust",
    "AuthenticodeVerification",
    "CODE_SIGNING_EKU_OID",
    "LEGACY_INTEGRITY_BRIDGE_THUMBPRINTS",
    "LEGACY_PIN_COMPATIBILITY_VERSION",
    "PUBLIC_RELEASE_SIGNER_THUMBPRINTS",
    "TRANSITION_BRIDGE_VERSION",
    "TRANSITION_BRIDGE_VERSION_ENV",
    "classify_authenticode",
    "configured_transition_bridge_version",
    "expected_public_signer_thumbprints",
    "is_legacy_bridge_version",
    "normalize_thumbprint",
    "parse_thumbprints",
    "validate_build_signing_configuration",
    "verify_authenticode",
]
