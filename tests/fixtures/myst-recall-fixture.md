# Image processing pipeline

<!--
Recall-guardrail companion to myst-fixture.md. Every section here SHOULD still
fire its named rule after the false-positive remediations land. If any of
these warnings disappear, recall has been weakened.
-->

This pipeline ingests photographs, extracts EXIF data, and stores derived
thumbnails in object storage. Operators monitor the queue depth and retry
rate to catch backlog before it becomes user-visible.

## Configuring auth

<!--
TARGETS: Heading.InformationScent (recall guardrail)
EXPECT: warning. "Configuring auth" has no semantic overlap with "Image
processing pipeline" — a genuinely off-topic heading. The H1 has 3 content
words ("image", "processing", "pipeline") so h1_is_specific=True and the
rule does not short-circuit.
-->

Auth tokens come from the central identity provider. Rotate them every 90 days.

## Deploy the worker

<!--
TARGETS: Resilience.ErrorPathPresence (recall guardrail)
EXPECT: warning. Genuinely procedural section: verb-led heading, numbered
steps, "deploy" keyword, zero failure guidance.
-->

1. Build the worker image with `make image`.
2. Push the image to the registry.
3. Apply the Kubernetes manifest in `k8s/worker.yaml`.
4. Verify the pod reaches Running status.

## Local cohesion test

<!--
TARGETS: Cohesion.Break, Rhetoric.TrivializingLanguage (recall guardrails)
EXPECT: cohesion break between the two unrelated sentences below; trivializing
language warning on "simply".
-->

The pipeline supports JPEG, PNG, and HEIC inputs. Whales migrate thousands of
miles each year along well-established ocean corridors.

You can simply restart the worker to pick up new configuration.
