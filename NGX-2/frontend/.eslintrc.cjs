module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  ignorePatterns: ["dist", ".eslintrc.cjs", "node_modules"],
  parser: "@typescript-eslint/parser",
  plugins: ["react-refresh"],
  rules: {
    "react-refresh/only-export-components": [
      "warn",
      { allowConstantExport: true },
    ],
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "warn",
    "no-restricted-imports": [
      "error",
      {
        patterns: [
          {
            group: ["@/mock/*", "**/mock/*"],
            message: "Mock data must only be imported by service modules (src/services/*). Components should consume services via hooks.",
          },
        ],
      },
    ],
  },
  overrides: [
    {
      files: ["src/services/**/*.ts"],
      rules: { "no-restricted-imports": "off" },
    },
  ],
};
