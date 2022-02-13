module.exports = {
  "parser": "@typescript-eslint/parser",
  "parserOptions": {
    "project": "tsconfig.json",
    "tsconfigRootDir": __dirname,
  },
  "settings": {
    "react": {
      "pragma": "React",
      "version": "16.12"
    }
  },
  "extends": [
    "airbnb",
    "airbnb/hooks",
    "airbnb-typescript"
  ],
  "plugins": [
    "@typescript-eslint"
  ],
  "env": {
    "browser": true
  },
  "rules": {
    "max-len": ["error", 120, 2],
    "@typescript-eslint/quotes": ["error", "double"],
    // We are targeting ES5 or higher.
    "radix": ["error", "as-needed"],
    // TypeScript validates prop types, no need for this.
    "react/require-default-props": "off",
    // Pls
    "no-mixed-operators": "off",
    // Preact
    "react/react-in-jsx-scope": "off",
    "react/no-unknown-property": "off",
  }
};
