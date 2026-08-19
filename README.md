# ADK Retail Support Agent

Customer Order and Operations Agent for Cymbal Retail built with Google ADK (Agent Development Kit).

## Getting started

## Running the tests

In order to run the unit tests, you can use the following command:

```shell
uv run pytest -m unit
```

The integration tests need a Firestore database. You can automatically check, install, start, and seed the Firestore emulator with:

```shell
source ./scripts/setup-emulator.sh
```

> [!NOTE]  
> Sourcing the script (`source ./scripts/setup-emulator.sh`) sets `FIRESTORE_EMULATOR_HOST=127.0.0.1:8888` in your current shell and seeds it with initial test data.


And now you can run the integration tests:

```shell
uv run pytest -m integration
```

If you don't start the emulator (and not set the `FIRESTORE_EMULATOR_HOST`), the integration tests will use the current configured project and connect to a live (potentially test) database on Google Cloud.

### Running Agent Evaluations

To evaluate the agent end-to-end with the live Gemini model against evaluation datasets:

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

