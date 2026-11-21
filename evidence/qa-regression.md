# Regression checks and submission checklist

| Requirement from the course materials | Where to verify |
| --- | --- |
| Name contains class, group and student IDs | `Demo_N05_G02_524H0195_524H0191_524H0187.zip` |
| All demonstration source | `android/`, `backend/`, `tools/` and the build instructions in `README.md` |
| DOC/PDF describing the demo | Both formats under `report/`, based on the supplied course template |
| Environment, implementation, walkthrough, evidence, limitations and attributions | Technical report, Sections 1–7, and these raw evidence files |
| Repository URL | [GitHub repository](https://github.com/Towfienes/tdtu-is-n05-g02-secure-chat), linked from the report |
| Instructor read access | The repository is private. Access must be granted to the instructor’s confirmed GitHub account |

## Changes checked against the earlier build

**Draft on rotation.** Type `G02-DRAFT` into the pinned app, dismiss the keyboard, and rotate to landscape. The earlier build displayed the composer but the exact draft text was missing from UI Automator. The updated verifier requires the draft and the action controls to remain available, and checks the capture is actually landscape. It also checks a 360 dp portrait viewport at 125% text scale.

**Message submit.** The earlier backend responded to POST with only the new message, so Android made a second GET. The backend tests first failed when they expected the updated conversation. The revised backend returns the latest 30 messages in the POST response. The emulator verifier requires one POST 201 and no separate GET during the send checkpoint. It then checks that both Android variants see each other's messages through the same running backend.

**Regression coverage.** The same run still exercises the shared-CA A/B comparison, backup key, rejection of an untrusted CA, a failed send preserving the draft, startup with encrypted cache, offline refresh, the private Activity boundary, and cache tamper detection. The tests use only the lab server and synthetic data. See `results.json` and `android-instrumentation.txt`.
