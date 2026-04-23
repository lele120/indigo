#!/usr/bin/env bash
#
# Downloads a small demo corpus for the Document Intelligence Server.
# Mix of PDF + plain text, aligned with the financial-services scenario.
#
# URLs point to institutional sources and are reasonably stable,
# but verify each download below before demo'ing — sites occasionally
# reorganize. Failures in one download don't abort the rest.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${SCRIPT_DIR}/../samples"
mkdir -p "${OUT_DIR}"
cd "${OUT_DIR}"

# name | url
# NIST publications: large, well-structured, relevant to financial-services
# compliance (risk, security controls, privacy). Served plain from nvlpubs.
# EUR-Lex PDFs (GDPR/MiFID) are behind AWS WAF and cannot be fetched by curl.
PDFS=(
  "nist-cybersecurity-framework-1.1.pdf|https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.04162018.pdf"
  "nist-sp-800-53r5-security-privacy-controls.pdf|https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf"
  "nist-sp-800-171r2-protecting-cui.pdf|https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-171r2.pdf"
)

is_valid_pdf() {
  # %PDF = 0x25 0x50 0x44 0x46
  [[ -s "$1" ]] && [[ "$(head -c 4 "$1")" == "%PDF" ]]
}

ok=0
fail=0

for entry in "${PDFS[@]}"; do
  name="${entry%%|*}"
  url="${entry##*|}"
  if is_valid_pdf "${name}"; then
    echo "SKIP  ${name} (already present, $(du -h "${name}" | cut -f1))"
    ok=$((ok+1))
    continue
  fi
  rm -f "${name}"
  echo "GET   ${name}"
  if curl -fL --retry 2 --max-time 180 -A "Mozilla/5.0 (demo-corpus-downloader)" \
       -o "${name}" "${url}" && is_valid_pdf "${name}"; then
    echo "OK    ${name}  ($(du -h "${name}" | cut -f1))"
    ok=$((ok+1))
  else
    echo "FAIL  ${name}  <- not a valid PDF; verify URL: ${url}"
    rm -f "${name}"
    fail=$((fail+1))
  fi
done

# Plain-text samples (generated locally — covers the .txt requirement
# even if all downloads fail, and gives you something with obvious
# keywords to test BM25 vs vector retrieval).
cat > compliance-faq.txt <<'EOF'
Frequently Asked Questions — Compliance & Regulatory Operations

Q: What is the policy on insider trading?
A: Employees with access to material non-public information (MNPI) must
not trade in the securities of any issuer to which the MNPI relates.
Violations are reported to the Compliance Officer and may result in
termination and regulatory referral under MAR Article 14.

Q: When must a Suspicious Activity Report (SAR) be filed?
A: Under the Bank Secrecy Act, SARs must be filed within 30 calendar
days of detecting a suspicious transaction involving $5,000 or more.
Escalate to the AML team; do not tip off the customer.

Q: What is the retention period for client communications?
A: All electronic communications (email, chat, voice) related to
regulated activity must be retained for a minimum of 5 years in a
non-rewritable, non-erasable format (SEC Rule 17a-4(f)).

Q: How do I request approval for an outside business activity?
A: Submit Form OBA-01 to Compliance at least 10 business days before
engaging in the activity. Board seats and paid consulting require
written pre-approval from the CCO.

Q: What counts as a personal securities account that must be disclosed?
A: Any account in which the employee has direct or indirect beneficial
ownership, including accounts of spouse, dependents, and entities the
employee controls. Report within 10 days of account opening.
EOF

cat > onboarding-checklist.txt <<'EOF'
New Hire Onboarding Checklist — Week 1

Day 1
- Complete I-9 verification with HR by 10:00 AM
- Receive laptop, badge, and MFA hardware token
- Sign NDA, Code of Conduct, and Outside Business Activity attestation
- Complete mandatory Information Security 101 training module

Day 2
- AML / KYC foundations training (2 hours, LMS course ID AML-101)
- Insider Trading and Personal Account Dealing policy acknowledgement
- Book 1:1 with direct manager for Q1 objectives

Day 3
- Shadow a senior associate on a live client onboarding
- Review team runbook for incident response
- Request access to production systems via the Access Request Portal

Day 4
- Data Privacy and GDPR training (required for all EU-facing roles)
- Set up expense system and corporate card
- Introduce yourself in the #new-joiners Slack channel

Day 5
- Submit completed onboarding checklist to HR partner
- Attend new-hire Q&A with the COO (Fridays, 3:00 PM)
- Book trainings for Week 2: Market Abuse Regulation deep dive,
  Product 101, and Compliance Monitoring Program overview
EOF

echo ""
echo "=========================================="
echo "Downloads: ${ok} ok, ${fail} failed"
echo "Generated: compliance-faq.txt, onboarding-checklist.txt"
echo "Output dir: ${OUT_DIR}"
echo "=========================================="
ls -lh "${OUT_DIR}"
