# Jitters the Night Before the Big Day: Autonomous Software Factories and the "Blind Agent" Problem

*By Marty McEnroe*

There is a moment right before you push the button on an autonomous software factory that feels exactly like waiting for a space launch. The specification is locked, the environment is provisioned, and the agentic orchestrator is idling. 

You ask yourself: *Did I tell the AI enough? Or did I tell it too much?*

This is the classic engineering dilemma—Big Design Up Front (BDUF) versus Agile Iteration—but when you are delegating the actual *writing of the code* to an AI agent like AssemblyZero, the stakes of that dilemma change completely.

## The Dream of the Clean Room

My ultimate goal with AssemblyZero isn't just to write code faster. It's to prove that we can build a fully functioning desktop application (in this case, an app called BoostGauge) and publish it to PyPI without a single human keystroke during the run. 

To prove this to the world—to hit "record" and capture a pristine, flawless run from specification to deployed product—the factory execution must be **idempotent**. A single run of an AI agent often mutates code, changes issue states, and leaves a repository "dirty." If it fails, you can't just run it again; you have to manually unpick what it did.

So, I built the "Clean Room" architecture: 
1. **The Blueprint (Immutable):** A static directory containing purely human-readable specifications (`issues.json`, architectural constraints, and pre-rendered test assets).
2. **The Factory Floor (Volatile):** An ephemeral repository that is wiped clean and re-hydrated from the Blueprint on every single run. 

You press the button. The Blueprint flows into the Factory Floor. AssemblyZero boots up, reads the Blueprint, and starts building.

## The "Let Her Rip" vs. "Tighten the Screws" Debate

But here is where the pre-launch jitters hit. Right now, my Blueprint consists of "human" issues. Things like:
> *"Make it an always-on-top, draggable, frameless window. Make it look good."*

If I hit the button now, the "Let Her Rip" philosophy dictates that the AI will try to build exactly that. It will write a Python GUI using `tkinter`. It will try to make it transparent.

But here is the catch: **AI Agents are Blind.**

AssemblyZero cannot look at a computer screen. If `tkinter` renders the background black instead of transparent, or if a resource polling loop freezes the main GUI thread, the agent won't know unless the code actively crashes. It will proudly declare success on an unusable app.

If I let her rip, the agent might waste hours building a monolithic GUI that it ultimately cannot write automated tests for. 

The alternative is the "Tighten the Screws" philosophy. This means halting the launch and injecting aggressive, highly technical architectural constraints into the Blueprint *before* the AI is allowed to write a single line of code. 

I have to tell the AI:
1. **Decouple the Visuals:** You must write pure math functions for the application logic and test them independently.
2. **Golden Image Testing:** You must use a library like `Pillow` to render the GUI headlessly to a `.png` file. You will test the visuals by mathematically hashing the output image against a pre-approved "Golden Image" in the Blueprint. 
3. **Threading Boundaries:** You must isolate the UI event loop from the system data collectors using strict queues.

## Why This Matters

This isn't just about building a system monitor. This is about discovering the operating system of the future. 

If we can solve the idempotent execution of autonomous agents—if we can learn exactly how much specification an AI needs to cross the finish line without human intervention—we are no longer just programmers. We are factory managers. 

So tonight, I'm getting three different AI agents to review my Blueprint and draft those final guardrail issues. Once they are injected into the Clean Room, the countdown resumes.

We hit the big red button. We wave the start flag. We see what the factory can build.

*(If you are building the future of autonomous engineering, star [AssemblyZero on GitHub](https://github.com/martymcenroe/AssemblyZero), or reach out if your team needs to understand how to manage and deploy agentic workflows.)*