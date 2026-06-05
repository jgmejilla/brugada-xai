# CS19X-Brugada-Syndrome-Classifier

Elijah Mejilla and Edzo Acyatan
CS 198, UP Diliman - Department of Computer Science

## Structure
- `/app`: the demonstration app, built with SvelteKit, that provides a web interface with the model
- `/data`: contains raw datasets before any preprocessing occurs
- `/papers`: clinical papers used for RAG
- `/preprocess`: prepares samples from `/data` and places them in `/samples`
- `/pipeline`: contains the end-to-end model
- `/requirements`: for setting up virtual environments depending on OS/terminal
- `/results`: contains results separated by date
- `/samples`: contains the prepared samples to be used in `/pipeline`
