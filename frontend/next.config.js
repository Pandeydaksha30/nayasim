/** @type {import('next').NextConfig} */
module.exports = {
  // pdf-parse loads pdf.js's worker file from its own folder at runtime.
  // Bundling it breaks that path, so load it from node_modules instead.
  serverExternalPackages: ['pdf-parse'],

  // Don't write AGENTS.md / CLAUDE.md into the project on `next dev`.
  agentRules: false,
};
