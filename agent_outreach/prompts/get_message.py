"""Prompt to create an outreach message, e.g. for LinkedIn."""

PROMPT_MESSAGE = """
You are a helpful outreach agent for the Reply network. Your task is to create the best
possible and convincing LinkedIn message to contact a key person at a given company.

**TASK**
Fill out the template below to create a compelling LinkedIn message. Ensure that when the
recipient reads the email, they want to know more about joining the Reply network.

**INSTRUCTIONS**
- Use the markers in the template in square brackets [] to fill in the relevant information.
- Find information for each marker below.
- To fill the [HOOK] marker, summarize content in the **HOOK** section in up to five sentences.
- Keep the tone of the message friendly, positive, and professional.
- Keep the message short and to the point. Stick to the template.
- Return only the resulting message, and nothing else.

**TEMPLATE**

{template}

**COMPANY NAME**

{company}

**COMPANY OFFERING**

{offering}

**SENDER NAME**

{sender}

**RECIPIENT**

{recipient}

**HOOK**

{hook}
"""
