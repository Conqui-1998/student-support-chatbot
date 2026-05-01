# Moodle Module Content Setup

The chatbot can now route questions to a module-specific knowledge base.

## Moodle script tag

Use a `data-module-key` attribute in the theme-injected script tag:

```html
<script
  src="https://prototype-student-support-chatbot.onrender.com/static/widget.js"
  data-page-contains="view.php?id=2684"
  data-module-key="test-module">
</script>
```

## Content location

Store generated module content here:

`data/modules/<module-key>/`

Example:

`data/modules/test-module/`

## File format

Put plain markdown files in that folder.

Each `.md` file can contain:

- `Title: ...`
- `URL: ...`
- `Category: ...`
- body text after a blank line

The RAG loader will chunk and index those files for the matching `module_key`.
