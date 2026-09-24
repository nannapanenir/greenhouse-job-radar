"""Skill lexicon + whole-word matching helpers.

KNOWN_SKILLS is copied verbatim from resume-tailor/public/js/mockData.js
(the local fallback engine). EXTRA_TECH_TERMS widens what the truth
validator recognises as a technology claim; it contains only unambiguous
tech names (no plain English words like "Go", "Rust", "Swift").
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable

KNOWN_SKILLS = [
    'Angular', 'Angular 19', 'React', 'TypeScript', 'JavaScript', 'Node.js',
    'REST APIs', 'GraphQL', 'PrimeNG', 'NgRx', 'RxJs', 'Redux', 'HTML', 'CSS',
    'SCSS', 'CI/CD', 'Jenkins', 'Git', 'Agile', 'Scrum', 'AWS', 'Azure', 'GCP',
    'Docker', 'Kubernetes', 'Terraform', 'Microservices', 'SQL', 'MongoDB',
    'PostgreSQL', 'Java', 'Spring Boot', 'Python', 'Jest', 'Cypress', 'Webpack',
]

EXTRA_TECH_TERMS = [
    'Vue', 'Vue.js', 'Svelte', 'Next.js', 'Nuxt', 'Tailwind', 'Storybook', 'Redux Toolkit', 'jQuery',
    'Django', 'Flask', 'FastAPI', 'Express', 'NestJS', 'Ruby on Rails', '.NET', 'C#', 'C++', 'Golang',
    'Kotlin', 'Scala', 'PHP', 'Laravel', 'Elixir', 'Haskell',
    'Kafka', 'RabbitMQ', 'Redis', 'Elasticsearch', 'Snowflake', 'BigQuery', 'Redshift', 'DynamoDB',
    'Cassandra', 'MySQL', 'Oracle', 'Spark', 'Airflow', 'Hadoop', 'dbt', 'Databricks',
    'PyTorch', 'TensorFlow', 'scikit-learn', 'LangChain', 'LlamaIndex', 'Hugging Face', 'OpenAI',
    'LLM', 'LLMs', 'RAG', 'GenAI', 'Generative AI', 'Machine Learning', 'MLOps', 'NLP', 'Computer Vision',
    'Ansible', 'Helm', 'Prometheus', 'Grafana', 'Datadog', 'Splunk', 'New Relic', 'OpenTelemetry',
    'Playwright', 'Selenium', 'Mocha', 'Vitest', 'Jasmine', 'Karma',
    'Figma', 'Tableau', 'Power BI', 'Salesforce', 'ServiceNow', 'SAP',
    'GitHub Actions', 'GitLab CI', 'CircleCI', 'Bitbucket', 'Jira',
    'gRPC', 'WebSockets', 'OAuth', 'SAML', 'Okta', 'Linux', 'Bash', 'PowerShell',
    'Serverless', 'Cloudflare', 'Vercel', 'Firebase', 'Supabase',
]

# JS escapeRegExp character class, reused for identical escaping.
_SPECIAL = re.compile(r"([.*+?^${}()|\[\]\\])")


def escape(text: str) -> str:
    return _SPECIAL.sub(r"\\\1", text)


@lru_cache(maxsize=4096)
def word_regex(term: str) -> re.Pattern[str]:
    """``\\bterm\\b`` like the JS engine (ASCII word boundaries, case-insensitive).

    Terms starting/ending with a non-word char (".NET", "C++", "C#") use
    lookarounds instead, since ``\\b`` never matches there.
    """
    body = escape(term)
    start = r"\b" if re.match(r"\w", term, re.ASCII) else r"(?<![\w])"
    end = r"\b" if re.search(r"\w$", term, re.ASCII) else r"(?![\w])"
    return re.compile(start + body + end, re.IGNORECASE | re.ASCII)


def contains_term(text: str, term: str) -> bool:
    return bool(term) and bool(word_regex(term).search(text or ""))


def extract_skills_from_text(text: str, lexicon: Iterable[str] = KNOWN_SKILLS) -> list[str]:
    """Port of mockData.extractSkillsFromText (order = lexicon order, unique)."""
    lower = (text or "").lower()
    found: list[str] = []
    for skill in lexicon:
        if contains_term(lower, skill) and skill not in found:
            found.append(skill)
    return found


def tech_lexicon(extra: Iterable[str] = ()) -> list[str]:
    seen, terms = set(), []
    for term in [*KNOWN_SKILLS, *EXTRA_TECH_TERMS, *extra]:
        key = term.strip().lower()
        if key and key not in seen:
            seen.add(key)
            terms.append(term.strip())
    return terms
