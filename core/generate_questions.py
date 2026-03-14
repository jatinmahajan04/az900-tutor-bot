"""
One-time script: generates 3 AZ-900 questions per exam topic using Claude.
Saves to data/question_bank.json  (~171 questions covering all exam objectives).

Run: python -m core.generate_questions
"""

import json
import time
import os
from pathlib import Path
import anthropic

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "question_bank.json"

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Every testable bullet from the Jan 2026 AZ-900 study guide
TOPICS = [
    # ── Cloud Concepts ────────────────────────────────────────────────────────
    {"domain": "Cloud Concepts", "topic": "Definition of cloud computing"},
    {"domain": "Cloud Concepts", "topic": "Shared responsibility model"},
    {"domain": "Cloud Concepts", "topic": "Public cloud model"},
    {"domain": "Cloud Concepts", "topic": "Private cloud model"},
    {"domain": "Cloud Concepts", "topic": "Hybrid cloud model"},
    {"domain": "Cloud Concepts", "topic": "Consumption-based pricing model"},
    {"domain": "Cloud Concepts", "topic": "Cloud pricing models comparison"},
    {"domain": "Cloud Concepts", "topic": "Serverless computing"},
    {"domain": "Cloud Concepts", "topic": "High availability and scalability"},
    {"domain": "Cloud Concepts", "topic": "Reliability and predictability in the cloud"},
    {"domain": "Cloud Concepts", "topic": "Security and governance benefits"},
    {"domain": "Cloud Concepts", "topic": "Manageability in the cloud"},
    {"domain": "Cloud Concepts", "topic": "Infrastructure as a Service (IaaS)"},
    {"domain": "Cloud Concepts", "topic": "Platform as a Service (PaaS)"},
    {"domain": "Cloud Concepts", "topic": "Software as a Service (SaaS)"},

    # ── Azure Architecture and Services ───────────────────────────────────────
    {"domain": "Azure Architecture and Services", "topic": "Azure regions and region pairs"},
    {"domain": "Azure Architecture and Services", "topic": "Sovereign regions"},
    {"domain": "Azure Architecture and Services", "topic": "Availability zones"},
    {"domain": "Azure Architecture and Services", "topic": "Azure datacenters"},
    {"domain": "Azure Architecture and Services", "topic": "Azure resources and resource groups"},
    {"domain": "Azure Architecture and Services", "topic": "Azure subscriptions"},
    {"domain": "Azure Architecture and Services", "topic": "Management groups"},
    {"domain": "Azure Architecture and Services", "topic": "Hierarchy of resource groups, subscriptions, and management groups"},
    {"domain": "Azure Architecture and Services", "topic": "Containers vs virtual machines vs functions"},
    {"domain": "Azure Architecture and Services", "topic": "Azure Virtual Machines and VM Scale Sets"},
    {"domain": "Azure Architecture and Services", "topic": "Availability sets"},
    {"domain": "Azure Architecture and Services", "topic": "Azure Virtual Desktop"},
    {"domain": "Azure Architecture and Services", "topic": "Application hosting options: web apps, containers, VMs"},
    {"domain": "Azure Architecture and Services", "topic": "Azure virtual networks and subnets"},
    {"domain": "Azure Architecture and Services", "topic": "Virtual network peering"},
    {"domain": "Azure Architecture and Services", "topic": "Azure DNS"},
    {"domain": "Azure Architecture and Services", "topic": "Azure VPN Gateway"},
    {"domain": "Azure Architecture and Services", "topic": "Azure ExpressRoute"},
    {"domain": "Azure Architecture and Services", "topic": "Public and private endpoints"},
    {"domain": "Azure Architecture and Services", "topic": "Azure Storage services comparison"},
    {"domain": "Azure Architecture and Services", "topic": "Azure Blob Storage access tiers"},
    {"domain": "Azure Architecture and Services", "topic": "Storage redundancy options (LRS, ZRS, GRS, GZRS)"},
    {"domain": "Azure Architecture and Services", "topic": "Storage account types"},
    {"domain": "Azure Architecture and Services", "topic": "Moving files: AzCopy, Azure Storage Explorer, Azure File Sync"},
    {"domain": "Azure Architecture and Services", "topic": "Migration: Azure Migrate and Azure Data Box"},
    {"domain": "Azure Architecture and Services", "topic": "Microsoft Entra ID (Azure Active Directory)"},
    {"domain": "Azure Architecture and Services", "topic": "Microsoft Entra Domain Services"},
    {"domain": "Azure Architecture and Services", "topic": "Single sign-on (SSO)"},
    {"domain": "Azure Architecture and Services", "topic": "Multifactor authentication (MFA) and passwordless"},
    {"domain": "Azure Architecture and Services", "topic": "External identities in Azure"},
    {"domain": "Azure Architecture and Services", "topic": "Microsoft Entra Conditional Access"},
    {"domain": "Azure Architecture and Services", "topic": "Azure role-based access control (RBAC)"},
    {"domain": "Azure Architecture and Services", "topic": "Zero Trust security model"},
    {"domain": "Azure Architecture and Services", "topic": "Defense-in-depth model"},
    {"domain": "Azure Architecture and Services", "topic": "Microsoft Defender for Cloud"},

    # ── Azure Management and Governance ──────────────────────────────────────
    {"domain": "Azure Management and Governance", "topic": "Factors that affect Azure costs"},
    {"domain": "Azure Management and Governance", "topic": "Azure Pricing Calculator"},
    {"domain": "Azure Management and Governance", "topic": "Azure Cost Management"},
    {"domain": "Azure Management and Governance", "topic": "Resource tags in Azure"},
    {"domain": "Azure Management and Governance", "topic": "Microsoft Purview"},
    {"domain": "Azure Management and Governance", "topic": "Azure Policy"},
    {"domain": "Azure Management and Governance", "topic": "Resource locks"},
    {"domain": "Azure Management and Governance", "topic": "Azure portal"},
    {"domain": "Azure Management and Governance", "topic": "Azure Cloud Shell, CLI, and PowerShell"},
    {"domain": "Azure Management and Governance", "topic": "Azure Arc"},
    {"domain": "Azure Management and Governance", "topic": "Infrastructure as code (IaC)"},
    {"domain": "Azure Management and Governance", "topic": "Azure Resource Manager (ARM) and ARM templates"},
    {"domain": "Azure Management and Governance", "topic": "Azure Advisor"},
    {"domain": "Azure Management and Governance", "topic": "Azure Service Health"},
    {"domain": "Azure Management and Governance", "topic": "Azure Monitor, Log Analytics, and Application Insights"},
]


PROMPT_TEMPLATE = """You are writing AZ-900 Azure Fundamentals exam practice questions.

Topic: {topic}
Domain: {domain}

Generate exactly 3 scenario-based multiple-choice questions about this topic.
Each question must:
- Present a realistic business or technical scenario (2-3 sentences)
- Have exactly 4 options labeled A, B, C, D
- Have exactly one correct answer
- Test a nuanced aspect — avoid trivially obvious questions

Use this exact format for each question (no extra text between questions):

QUESTION_START
TOPIC: {topic}
QUESTION: <scenario and question>
A) <option>
B) <option>
C) <option>
D) <option>
ANSWER: <single letter>
EXPLANATION: <1-2 sentences why the answer is correct>
QUESTION_END"""


def parse_questions(raw: str, domain: str) -> list[dict]:
    questions = []
    blocks = raw.split("QUESTION_START")
    for block in blocks:
        if "QUESTION_END" not in block:
            continue
        block = block[:block.index("QUESTION_END")].strip()
        lines = block.splitlines()
        q = {"domain": domain, "topic": "", "question": "", "options": {}, "answer": "", "explanation": ""}
        current = None
        for line in lines:
            line = line.strip()
            if line.startswith("TOPIC:"):
                q["topic"] = line[6:].strip()
            elif line.startswith("QUESTION:"):
                q["question"] = line[9:].strip()
                current = "question"
            elif line.startswith(("A)", "B)", "C)", "D)")):
                q["options"][line[0]] = line[3:].strip()
                current = None
            elif line.startswith("ANSWER:"):
                q["answer"] = line[7:].strip().upper()[:1]
            elif line.startswith("EXPLANATION:"):
                q["explanation"] = line[12:].strip()
            elif current == "question" and line and not any(
                line.startswith(p) for p in ("A)", "B)", "C)", "D)", "ANSWER:", "EXPLANATION:")
            ):
                q["question"] += " " + line
        if q["question"] and q["answer"] and len(q["options"]) == 4:
            questions.append(q)
    return questions


def generate_for_topic(domain: str, topic: str) -> list[dict]:
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1200,
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(topic=topic, domain=domain)}],
    )
    return parse_questions(response.content[0].text, domain)


def run():
    bank: dict[str, list] = {
        "Cloud Concepts": [],
        "Azure Architecture and Services": [],
        "Azure Management and Governance": [],
    }

    total = len(TOPICS)
    for i, item in enumerate(TOPICS, 1):
        domain, topic = item["domain"], item["topic"]
        print(f"[{i}/{total}] {topic}...", end=" ", flush=True)
        try:
            questions = generate_for_topic(domain, topic)
            bank[domain].extend(questions)
            print(f"✓ {len(questions)} questions")
        except Exception as e:
            print(f"✗ ERROR: {e}")
        time.sleep(0.3)  # gentle rate limiting

    total_q = sum(len(v) for v in bank.values())
    OUTPUT_PATH.write_text(json.dumps(bank, indent=2))
    print(f"\nDone. {total_q} questions saved to {OUTPUT_PATH}")
    for domain, qs in bank.items():
        print(f"  {domain}: {len(qs)} questions")


if __name__ == "__main__":
    run()
