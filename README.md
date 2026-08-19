# ADK Retail Support Agent

Customer Order and Operations Agent for Cymbal Retail built with Google ADK (Agent Development Kit).

## Getting started

## Running the tests

In order to run the unit tests, you can use the following command:

```shell
uv run pytest -m unit
```

The integration tests need a Firestore database. You can start the emulator using the following command:

```shell
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8888
gcloud emulators firestore start --host-port=$FIRESTORE_EMULATOR_HOST
```

> [!NOTE]  
> The tests need the `FIRESTORE_EMULATOR_HOST` in emulation mode, so if you start another shell, make sure to set that variable.

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
