# Contributing

Thank you for helping to keep the guidebook accurate! Most contributions are corrections or
additions to **services** and **guidebook steps**. You can make them directly in your browser.

## Suggest a change to a service or step (in the browser)

1. Find the file in [`data/`](data/):
   - services: `data/services/<country>/…yaml` (for example `data/services/at/permit-building-code.yaml`)
   - guidebook steps: `data/steps/<phase>/…yaml`
2. Open the file and click the **pencil icon** ("Edit this file"). GitHub asks you to create a
   copy (a "fork") the first time — that is expected.
3. Change the text. Keep the `field: value` structure; see [data/README.md](data/README.md)
   for what each field means.
4. Click **Commit changes…**, describe what you changed and why (ideally with a source, such as
   the official page), then **Propose changes** and **Create pull request**.

Automatic checks then verify the file. If something is wrong (for example a missing field or a
link that does not start with `https://`), the check shows the file and the problem. After a
maintainer or the reviewer for that country has approved and merged your change, it appears on
the live site within a few minutes.

**Adding a new service?** Copy an existing file from the same country folder, give it a new
name (lowercase words joined by `-`, e.g. `grid-connection-request.yaml`) and edit it.

**Removing a service?** Delete its file, or add `active: false` to hide it. Services that are
already used in projects are hidden, never deleted, so project records stay intact.

**Do not rename files.** The file name is the service's identity; a renamed file counts as a
removed and a new service.

## Prefer not to edit files?

Open an issue with the **"Suggest a service change"** form and describe the change. A maintainer
will turn it into a pull request.

## Guidelines

- Only publish information that is public: no personal names, private email addresses or phone
  numbers of individuals. Names of public bodies and companies offering a service are fine.
- Write the main fields in English. Keep the country's own terms in brackets where helpful,
  e.g. "building notification (Bauanzeige)".
- Add or correct the translation in the country's language in the same file (the `de:`,
  `bg:`, `fr:`, `hr:` or `it:` block, see [data/README.md](data/README.md#translations)).
  Many translations are drafts: if you are a native speaker and have checked one, set
  `reviewed: true`. If you change an English text, update the translation as well.
- Link to official sources (`https://…`) where possible.
- Keep `summary` short (max. 500 characters); put details into `description`.

## Code contributions

Bug reports and improvements to the application are welcome as issues or pull requests. See the
[README](README.md) for the local setup; please run `python manage.py test` before opening a pull
request. By contributing you agree that your contribution is licensed under the
[EUPL-1.2](LICENSE).
