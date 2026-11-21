"""Generate disposable localhost TLS fixtures and Android public trust resources."""

import base64
import hashlib
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKI = ROOT / ".lab/pki"
APP = ROOT / "android/app"


def openssl(*args, data=None):
    return subprocess.run(
        ["openssl", *map(str, args)], input=data, stdout=subprocess.PIPE, check=True
    ).stdout


def main():
    if PKI.exists():
        raise SystemExit(
            "Fixtures already exist. Keep them together with the APKs built from them."
        )
    PKI.parent.mkdir(mode=0o700, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=PKI.parent) as directory:
        stage = Path(directory)
        for ca in ("lab", "other"):
            openssl(
                "req",
                "-x509",
                "-newkey",
                "ec",
                "-pkeyopt",
                "ec_paramgen_curve:P-256",
                "-nodes",
                "-sha256",
                "-days",
                "30",
                "-subj",
                f"/CN=TDTU Demo {ca} CA",
                "-addext",
                "basicConstraints=critical,CA:TRUE",
                "-addext",
                "keyUsage=critical,keyCertSign,cRLSign",
                "-keyout",
                stage / f"{ca}.key",
                "-out",
                stage / f"{ca}.crt",
            )
        extensions = stage / "server.ext"
        extensions.write_text(
            "subjectAltName=DNS:localhost\nbasicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\n"
        )
        pins = {}
        for name in ("a", "b", "backup", "untrusted"):
            ca = "other" if name == "untrusted" else "lab"
            key = stage / f"{name}.key"
            csr = stage / f"{name}.csr"
            cert = stage / f"{name}.crt"
            openssl(
                "req",
                "-new",
                "-newkey",
                "ec",
                "-pkeyopt",
                "ec_paramgen_curve:P-256",
                "-nodes",
                "-subj",
                "/CN=localhost",
                "-keyout",
                key,
                "-out",
                csr,
            )
            openssl(
                "x509",
                "-req",
                "-in",
                csr,
                "-CA",
                stage / f"{ca}.crt",
                "-CAkey",
                stage / f"{ca}.key",
                "-CAcreateserial",
                "-days",
                "14",
                "-sha256",
                "-extfile",
                extensions,
                "-out",
                cert,
            )
            openssl(
                "verify",
                "-CAfile",
                stage / f"{ca}.crt",
                "-verify_hostname",
                "localhost",
                cert,
            )
            public = openssl("x509", "-in", cert, "-pubkey", "-noout")
            der = openssl("pkey", "-pubin", "-outform", "DER", data=public)
            pins[name] = base64.b64encode(hashlib.sha256(der).digest()).decode()
        assert len(set(pins.values())) == 4
        PKI.mkdir(mode=0o700)
        for path in stage.glob("*"):
            if path.suffix in {".crt", ".key"}:
                path.rename(PKI / path.name)
    for flavor in ("baseline", "pinned"):
        res = APP / "generated" / flavor
        (res / "raw").mkdir(parents=True, exist_ok=True)
        (res / "xml").mkdir(exist_ok=True)
        (res / "raw/lab_ca.pem").write_bytes((PKI / "lab.crt").read_bytes())
        pin_set = ""
        if flavor == "pinned":
            pin_set = f"""    <pin-set>
      <pin digest="SHA-256">{pins["a"]}</pin>
      <pin digest="SHA-256">{pins["backup"]}</pin>
    </pin-set>
"""
        (
            res / "xml/network_security_config.xml"
        ).write_text(f"""<network-security-config>
  <base-config cleartextTrafficPermitted="false" />
  <domain-config cleartextTrafficPermitted="false">
    <domain includeSubdomains="false">localhost</domain>
    <trust-anchors>
      <certificates src="@raw/lab_ca" />
    </trust-anchors>
{pin_set}  </domain-config>
</network-security-config>
""")
    print(
        "TLS fixtures ready: A, B, backup, and untrusted. Private keys are in .lab/pki."
    )


if __name__ == "__main__":
    main()
