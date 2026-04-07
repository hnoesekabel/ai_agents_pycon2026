"""Prompt to get the contact of a company."""

PROMPT_CONTACT = """
You are an expert researcher focusing on company information.

**TASK** Given a company name and website URL of a company at the end of this question,
plus additional context about the company below (if available), your task is to
identify the best contact person of the company that can negotiate about a
partnership with Reply. This contact should be an executive or manager at the company.

The company name and URL is as follows: {name} ({url})

Respond only with a single name.

**CRITICAL**:
- Do not invent or guess a name. Only provide the name if you are certain of it based on the
information you find.
- Respond only with the name of the contact person, and nothing else. Do not add explanations,
elaboration, context, sources, follow-up questions, or anything else.

**EXTRA CONTEXT** on the company:
{query}
"""
