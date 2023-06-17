# Tree of thoughts
A LMQL implementation of something like tree of thoughts. Applies a natural selection process to steer reasoning and constrain the results.

Many many improvements to be made.

## Features
I meant this to be as "engineerable" as possible. Each tree instance is configured to solve a specific problem, and be used as a function. It can apply a callback function to the result so it doesn't necessarily have to return text.

Some of the main features:
- Asynchronous
- Configurable
- Prompt-based and programmatic result validation

Some planned features:
- Multiple arguments and argument types
- Feature weighting: option to assign relative importance to selection criteria
- Dynamic width: method for determining how many branches should stem from each thought

## How it works
Each iteration consists of a review phase, a generation phase, an evaluation phase.
- **Selection:** The top-k scoring lines of thought are selected
- **Review:** Selected lines of thought are checked to see if they contain an answer.
- **Generation:**  A fixed number of branching thoughts are generate from selected leaf thoughts. If a selected leaf contains an answer, a conclusion is generated instead.
- **Evaluation:** New thoughts are scored against defined criteria to determine the relative strength of the threads. If any conclusions were generated, they are validated and returned if they pass. 

## Usage
For now see the `examples` folder to get a sense of it. In a nutshell there's three configurations: one for the initial prompt, one that governs the reasoning dynamics (evaluation, answer recognition), and one that describes how answer attempts are handled (conclusion generation, callbacks, validation).

