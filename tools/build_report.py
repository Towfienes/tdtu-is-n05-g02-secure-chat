"""Fill the course template from the recorded demonstration."""

import argparse
import json
from io import BytesIO
from pathlib import Path
from textwrap import dedent

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "android/app/src/main/java/vn/tdtu/securechat"
EVIDENCE = ROOT / "evidence"


def source(name, start, end):
    text = (JAVA / name).read_text()
    begin = text.index(start)
    return dedent(text[begin : text.index(end, begin)]).strip()


def make_report(template, output, repository):
    evidence = json.loads((EVIDENCE / "results.json").read_text())
    tests = evidence["tests"]
    fixtures = json.loads((EVIDENCE / "certificate-fixtures.json").read_text())
    pins = {
        item["fixture"]: item["spki_sha256"] for item in fixtures if item["matches_pin"]
    }
    assert set(pins) == {"a", "backup"}
    assert len(tests) == 16 and all(test["status"] == "PASS" for test in tests)
    document = Document(template)
    body = document.element.body
    table = document.tables[0]._element
    for element in list(body):
        if element is not table and element.tag != qn("w:sectPr"):
            body.remove(element)

    for name, font, size, bold, before, after in (
        ("Demo Body", "Times New Roman", 12, False, 0, 8),
        ("Demo Section", "Times New Roman", 15, True, 13, 7),
        ("Demo Subsection", "Times New Roman", 12, True, 9, 4),
        ("Demo Code", "Liberation Mono", 8.5, False, 1, 2),
        ("Demo Caption", "Times New Roman", 10, False, 4, 5),
    ):
        style = document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.font.name = font
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.color.rgb = RGBColor(22, 22, 22)
        fmt = style.paragraph_format
        fmt.space_before = Pt(before)
        fmt.space_after = Pt(after)
        fmt.line_spacing = 1.13
        fmt.keep_with_next = name in ("Demo Section", "Demo Subsection")

    for paragraph in document.tables[0].cell(0, 1).paragraphs:
        if paragraph.text.startswith("Instructor"):
            paragraph.clear()
            paragraph.add_run("Instructor: Huynh Ngoc Tu, Ph.D.").font.size = Pt(12)

    document.core_properties.title = "Secure Android Chat Final Demonstration"
    document.core_properties.author = (
        "Ngô Lâm Tiến; Nguyễn Công Thành; Võ Huỳnh Duy Tân"
    )
    section = document.sections[0]
    footer = section.footer.paragraphs[0]
    footer.clear()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)

    def p(value):
        return document.add_paragraph(value, "Demo Body")

    def h(value):
        return document.add_paragraph(value, "Demo Section")

    def sub(value):
        return document.add_paragraph(value, "Demo Subsection")

    def code(value):
        paragraph = document.add_paragraph(value, "Demo Code")
        paragraph.paragraph_format.keep_together = True
        shade = OxmlElement("w:shd")
        shade.set(qn("w:fill"), "F1F1F1")
        paragraph._p.get_or_add_pPr().append(shade)

    def pictures(figures):
        layout = document.add_table(rows=1, cols=len(figures))
        layout.autofit = False
        for cell, (filename, caption) in zip(
            layout.rows[0].cells, figures, strict=True
        ):
            cell.width = Inches(6.5 / len(figures))
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            with Image.open(EVIDENCE / (filename + ".png")) as screenshot:
                width, height = screenshot.size
                if filename == "intent-internal":
                    crop = screenshot.crop(
                        (0, int(height * 0.43), width, int(height * 0.58))
                    )
                else:
                    crop = screenshot.crop(
                        (0, int(height * 0.037), width, int(height * 0.37))
                    )
                cropped = BytesIO()
                crop.save(cropped, format="PNG")
            cropped.seek(0)
            paragraph.add_run().add_picture(cropped, width=Inches(3.10))
            paragraph.paragraph_format.keep_with_next = True
            label = cell.add_paragraph(caption, "Demo Caption")
            label.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p("Project topic: Topic 13 — Security in Client-Server Android Applications")
    p("Class N05  |  Group G02")
    p(
        "Ngô Lâm Tiến (leader) — 524H0195\nNguyễn Công Thành — 524H0191\nVõ Huỳnh Duy Tân — 524H0187"
    )
    if repository:
        paragraph = p("Repository link: ")
        link = OxmlElement("w:hyperlink")
        relation = paragraph.part.relate_to(
            repository, RELATIONSHIP_TYPE.HYPERLINK, is_external=True
        )
        link.set(qn("r:id"), relation)
        run = paragraph.add_run(repository)
        run.font.color.rgb = RGBColor(32, 77, 143)
        run.font.underline = True
        link.append(run._r)
        paragraph._p.append(link)
        p(
            "The public repository contains the source code and reproducible demo instructions."
        )
    else:
        p("Repository link: Pending publication to the group’s repository.")
        p("Submission draft — repository link and instructor access are pending.")

    h("1. Executive Summary")
    summary = (
        "Secure Android Chat is a native client and local HTTPS service that put the transport, component, "
        "and storage boundaries discussed in Topic 13 into practice. Two app builds use the same endpoint, "
        "test certificate authority, and hostname validation. The pinned build additionally checks the "
        "server public key. On Android 16, both builds accepted certificate A. The baseline also accepted "
        "certificate B, which had the same trusted issuer and hostname but a different key. The pinned build "
        "rejected B before the server received an HTTP request and resumed sending messages when A was restored. "
        "The backup key worked, and a certificate from an untrusted authority failed. The demonstration also "
        "verifies that Android prevents an external caller from opening the private message activity and that "
        "AES-GCM detects a modification to the encrypted message cache."
    )
    assert len(summary.split()) <= 200
    p(summary)
    h("2. Lab Environment and Tools Setup")
    p(
        f"Hardware and VM. Linux x86-64 host with KVM. Android Emulator 37.2.12, Android "
        f"{evidence['android_release']} (API {evidence['api']}, {evidence['architecture']})."
    )
    p(
        "Software. Android SDK 36, JDK 25.0.3, Gradle 9.8.1, Android Gradle Plugin 9.4.1, "
        "AndroidX Test Runner 1.7.0, Python 3.14, and OpenSSL 4.1.0. The backend uses the Python standard library."
    )
    p(
        "Network. Bind the backend to 127.0.0.1:8443 and forward emulator localhost:8443 to that port with ADB reverse. "
        "The app uses HTTPS for GET and POST /messages. All certificates and data are disposable lab fixtures."
    )

    h(
        "3. Core Implementation and Code Analysis"
    ).paragraph_format.page_break_before = True
    sub("a. Architecture and Flow Logic")
    p(
        "The app sends a synthetic message over HTTPS. Android validates the certificate chain and the hostname. "
        "The pinned build also matches a configured SPKI hash before the HTTPS request reaches the Python handler. "
        "The response is then sealed in private storage. A tap opens the details screen with the numeric message ID."
    )
    p(
        "Android chat → HTTPS client → ADB reverse → loopback message service\n"
        "Validated response → AES-GCM cache → private details screen"
    )
    p(
        "POST returns the bounded conversation snapshot created by the same server operation. "
        "The Android client renders that response directly. Backend logs confirmed that a successful send "
        "uses one HTTP request. A separate refresh still uses GET."
    )
    sub("b. Key Code Snippets and Explanation")
    sub("Snippet 1  Android network security policy")
    code(f"""<domain-config cleartextTrafficPermitted="false">
  <domain includeSubdomains="false">localhost</domain>
  <trust-anchors>
    <certificates src="@raw/lab_ca" />
  </trust-anchors>
  <pin-set>
    <pin digest="SHA-256">{pins["a"]}</pin>
    <pin digest="SHA-256">{pins["backup"]}</pin>
  </pin-set>
</domain-config>""")
    p(
        "The first two lines scope the policy to localhost and disallow cleartext. The trust anchor limits valid "
        "chains to the lab CA. The pin set adds the A and backup public keys to the acceptance policy. "
        "The baseline has the same trust anchor and hostname scope. The two Base64 values above are from "
        "the verified build. A fresh setup generates its own certificates and pin values."
    )
    sub("Snippet 2  Manifest boundary and explicit Intent")
    code(
        '<activity android:name=".DetailActivity" android:exported="false" />\n\n'
        'startActivity(new Intent(this, DetailActivity.class).putExtra("id", id));\n\n'
        + source(
            "DetailActivity.java", "    static int messageId(", "\n\n    @Override"
        )
    )
    p(
        "The manifest makes DetailActivity private to the app. The explicit Intent names the destination "
        "and passes only a numeric ID. The parser defaults missing or wrongly typed extras to −1 and "
        "rejects non-positive values. The Activity reads the matching message through the authenticated cache."
    )

    sub(
        "Snippet 3  Authenticated encryption of the cache"
    ).paragraph_format.page_break_before = True
    code(
        source(
            "MessageCache.java",
            '        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");',
            "\n        FileOutputStream",
        )
    )
    p(
        "The first line selects AES-GCM. The next line initializes encryption using the app’s Keystore key "
        "and lets the provider choose a fresh IV. The explicit size check enforces the cache format. "
        "The last line encrypts the UTF-8 message array and produces ciphertext with an authentication tag. "
        "AtomicFile writes the IV and sealed bytes together. On read, GCM checks the tag before returning plaintext."
    )
    sub("c. Algorithms and Cryptography Used")
    p(
        "TLS authenticates the server using X.509 chain validation and hostname matching. Pinning hashes the DER "
        "SubjectPublicKeyInfo with SHA-256, so a certificate reissue with the same key can still match. "
        "The backup pin authorizes a second key for controlled rotation. Certificate trust remains required."
    )
    p(
        "The local cache uses a 256-bit AES key generated by Android Keystore, a fresh 96-bit IV per write, "
        "and a 128-bit authentication tag. GCM provides confidentiality and integrity in one operation. "
        "Storing the IV beside the ciphertext lets the app decrypt it without persisting the secret key."
    )
    sub("Reproducing the demonstration")
    code("""python3 -m unittest discover -s backend
python3 tools/prepare_tls.py
(cd android && ./gradlew :app:assembleDebug :app:assemblePinnedDebugAndroidTest)
adb devices
python3 tools/verify_demo.py emulator-5562 evidence-local""")
    p(
        "Use the serial of your disposable API 36 emulator in the last command. The verifier installs both debug "
        "builds and the test APK, captures screenshots and logs, and removes the reverse mapping at exit. "
        "Read README.md for the prerequisites and the manual demo steps."
    )

    h(
        "4. Step-by-Step Demonstration Walkthrough"
    ).paragraph_format.page_break_before = True
    sub("Step 1  Initialization")
    p(
        "Generate the certificates, install both builds, and start the A fixture. Refresh Baseline and Pinned. "
        "The UI accepts TLS and the backend records a successful GET for each client."
    )
    sub("Step 2  Certificate Policy Comparison")
    p(
        "Restart the same backend with certificate B. Refresh Baseline, then try to send a sample message in Pinned. "
        "The name and issuer remain valid. Pinned logs “Pin verification failed” and the backend log has no HTTP handler entry."
    )
    pictures((("pinned-a", "Figure 1. Pinned with A accepts TLS."),))
    pictures(
        (
            ("baseline-b", "Figure 2. Baseline with B accepts TLS."),
            ("pinned-b", "Figure 3. Pinned with B refuses TLS."),
        )
    )
    p(
        "Evidence files: pinned-a.log, baseline-b.log, pinned-b.log, and pinned-b-logcat.txt. "
        "Figures crop the Android screenshots to the relevant region. The ZIP includes the full captures. The rejected POST provides a check of the send path, in addition to the successful refresh requests."
    )

    sub("Step 3  Verification and Recovery").paragraph_format.page_break_before = True
    p(
        "Restore A and send the sample message. Open its details from the conversation. Stop the backend and "
        "restart the app process to confirm that the conversation is restored from the encrypted cache."
    )
    pictures(
        (
            ("pinned-a-recovered", "Figure 4. Pinned sends again after restoring A."),
            ("cache-restored", "Figure 5. The app restores the cache after restart."),
        )
    )
    pictures(
        (("intent-internal", "Figure 6. Internal navigation shows message details."),)
    )
    p(
        "The OS separately returned Permission Denial for an external launch of DetailActivity. "
        "Instrumentation reopened the encrypted file, checked that repeated writes use different sealed bytes, "
        "and confirmed that a one-byte ciphertext change fails GCM authentication."
    )
    p(
        "Evidence files: pinned-a-recovered.log, intent-os-denial.txt, android-instrumentation.txt, "
        "and results.json."
    )

    sub("Observed Test Outcomes").paragraph_format.page_break_before = True
    results = document.add_table(rows=1, cols=2)
    results.style = "Table Grid"
    results.rows[0].cells[0].text = "Case"
    results.rows[0].cells[1].text = "Observed result"
    for test in tests:
        cells = results.add_row().cells
        cells[0].text = test["case"]
        cells[1].text = test["observed"]
    for i, row in enumerate(results.rows):
        row.cells[0].width = Inches(2.15)
        row.cells[1].width = Inches(4.35)
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.style = "Demo Caption"
                if i == 0:
                    for run in paragraph.runs:
                        run.bold = True
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    p(
        "Additional emulator evidence shows the two builds exchanging messages, the compact layout at "
        "125 percent font scale, and a draft retained after rotating to landscape. Full captures are included "
        "as cross-client-chat.png, compact-portrait.png, and landscape-draft.png."
    )
    h("5. Defense Mechanism").paragraph_format.page_break_before = True
    p(
        "The comparison shows why a valid chain and hostname alone can accept a different server key from "
        "the same authority. Adding a pin rejects that key before HTTP. Restoring the original key, or "
        "using the configured backup key with a trusted chain, permits connections again. The lab models "
        "the server identity check described in the midterm through controlled certificate substitution."
    )
    p(
        "A compromised pinned key could still authenticate a server. A compromised or instrumented client "
        "could expose plaintext after decryption. Production pinning requires a rotation and recovery plan, "
        "and cache protection depends on the integrity of the app and operating system."
    )

    h("6. Conclusion and Limitations")
    p(
        "Keeping the hostname, CA, address, and app behavior equal across the two builds was necessary to "
        "attribute the failure to pinning. During verification, logcat distinguished pin rejection from "
        "untrusted-CA rejection, while successful requests after recovery ruled out an unavailable backend."
    )
    p(
        "The demonstration uses an emulator, temporary certificates, and synthetic messages. The service has "
        "no user accounts, message persistence, or multi-user authorization. AES-GCM protects the local cache "
        "and detects modification. It does not guarantee confidentiality for plaintext already displayed "
        "by the application, or provide end-to-end message encryption."
    )
    p(
        "A production system would require authenticated identities and server authorization, certificate "
        "rotation procedures, retention controls, deployment monitoring, and device testing."
    )
    h("7. References and Attributions").paragraph_format.page_break_before = True
    p(
        "Group N05–G02. Midterm Theory Report, Topic 13, Security in Client-Server Android Applications."
    )
    p(
        "Android Developers. Network Security Configuration.\nhttps://developer.android.com/privacy-and-security/security-config"
    )
    p(
        "Android Developers. Android Keystore System.\nhttps://developer.android.com/privacy-and-security/keystore"
    )
    p(
        "Android Developers. Intents and Intent Filters.\nhttps://developer.android.com/guide/components/intents-filters"
    )
    p(
        "OpenAI Codex assisted in implementing the demonstration, writing verification code, and drafting this report. "
        "The reported outcomes were collected from the Android emulator and the local backend."
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repository")
    arguments = parser.parse_args()
    make_report(arguments.template, arguments.output, arguments.repository)
