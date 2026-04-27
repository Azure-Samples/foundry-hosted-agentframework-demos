# Host your agents on Foundry: Microsoft Agent Framework
27 April, 2026 | 10:00 AM - 11:00 AM (UTC-07:00) Pacific Time (US & Canada)

Format:
alt##LivestreamLivestream
Topic: Agents

Language: English

In this three-part series, we're showing you how to host your own agents on Microsoft Foundry.

In our first session, we'll deploy agents built with Microsoft Agent Framework (the successor of Autogen and Semantic Kernel).

Starting with a simple agent, we'll add Foundry tools like Code Interpreter, ground the agent in enterprise data with Foundry IQ, and finally deploy multi-agent workflows.

Along the way, we'll use the Foundry UI to interact with the hosted agent, testing it out in the playground and observing the traces from the reasoning and tool calls.

All code samples will be open-source and ready for easy deployment to your own Microsoft Foundry using the Azure Developer CLI.

After the stream, join office hours in the Microsoft Foundry Discord to ask follow-up questions.

## Demo plan: hosted agent

Once deployed, test each tool with these queries in the Foundry playground:

| # | Tool(s) expected | Query | Works? | Notes |
|---|---|---|---|---|
| 1 | KB retrieve | What PerksPlus benefits are there? | ✅ | Queries hrdocs |
| 2 | KB retrieve | What health plans does Zava offer? | ✅ | Queries healthdocs |
| 3 | KB retrieve | Can I use PerksPlus to pay for physical therapy, or is that covered by my health plan? | ✅ | Queries both hrdocs + healthdocs |
| 5 | get_enrollment_deadline_info | When does benefits enrollment open and close? | ✅  | |
| 6 | get_current_date + get_enrollment_deadline_info | How many days until enrollment opens? | ✅ | |
| 7 | KB + get_enrollment_deadline_info | What PerksPlus benefits are there, and when do I need to enroll by? | ✅ | Queries hrdocs |
| 8 | Web search | Search the web to find weather for El Cerrito today | | BUG: Playground won't render the response. Pritam investigating. |
| 9 | Web search | What was the latest US jobs report? | BUG: Same as other web search query, reported. | |
| 10 | Code interpreter | If I contribute 6% of a $120,000 salary to my 401k with a 50% employer match, how much total goes in per year? Use Code Interpreter to write Python code to calculate. | 🟡 | doesnt show up in traces linked from Chat playground. |
| 11 | Code interpreter | Make a pie chart of the Zava vacation tiers: Standard 2 weeks, Senior 4 weeks, Executive 6 weeks | 🟡 | BUG: Can't download the pie chart. Reported in Bug Bash. Also, doesnt show up in traces linked from Chat playground. |
| 12 | (none — decline) | What are the best exercises to reduce lower back pain? | 🟡 | It did not decline, still searched, and then triggered RAI filter |
