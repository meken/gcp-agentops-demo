# ADK Retail Support Agent

Customer Order and Operations Agent for Cymbal Retail built with Google ADK (Agent Development Kit). This is a very basic agent that's used for the Agents: Beyond the Basics gHack.

## Getting started

In order to install the dependencies in a new virtual environment you can use `uv sync`, just run the following command from the top level:

```shell
uv sync --dev  # also installes the pytest/ruff etc
```

For accessing the Gemini models you need to configure the authentication (assuming that you have configured Application Default Credentials in your environment):

```shell
export GOOGLE_GENAI_USE_ENTERPRISE=true
export GOOGLE_CLOUD_PROJECT=$(gcloud config get project)
```

## Running the tests

In order to run the unit tests, you can use the following command (the unittests don't access the database or the LLMs):

```shell
uv run pytest -m unit
```

The integration tests need a Firestore database. You can automatically install, start, and seed the Firestore emulator with:

```shell
source ./scripts/start-database-emulator.sh
```

> [!NOTE]  
> Sourcing the script (`source ./scripts/start-database-emulator.sh`) sets `FIRESTORE_EMULATOR_HOST=127.0.0.1:8888` in your current shell and seeds it with initial test data.

And now you can run the integration tests (the integration tests don't access LLMs):

```shell
uv run pytest -m integration
```

If you don't start the emulator (and not set the `FIRESTORE_EMULATOR_HOST`), the integration tests will use the current configured project and connect to a live (potentially test) database on Google Cloud.

### Running Agent Evaluations

To evaluate the agent end-to-end with the live Gemini model against evaluation datasets (note that the eval tests mock the database for idempotency):

```shell
uv run pytest -m eval
```

## Seeding the Live Google Cloud Database

To seed or reset the live Google Cloud Firestore database in your project:

```shell
# Uses $GOOGLE_CLOUD_PROJECT
./scripts/seed-cloud-database.sh

# Or with an explicit project ID:
./scripts/seed-cloud-database.sh --project your-gcp-project-id
```
