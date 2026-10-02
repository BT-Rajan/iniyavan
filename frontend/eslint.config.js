import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'

export default [
  {ignores: ['dist']},
  {
    files: ['src/**/*.{js,jsx}', 'public/**/*.js', '*.config.js'],
    languageOptions: {ecmaVersion: 'latest', sourceType: 'module', globals: {...globals.browser, ...globals.serviceworker}, parserOptions: {ecmaFeatures: {jsx: true}}},
    plugins: {react},
    settings: {react: {version: 'detect'}},
    rules: {...js.configs.recommended.rules, 'react/jsx-no-undef': 'error', 'react/jsx-uses-vars': 'error', 'react/jsx-uses-react': 'error'},
  },
]
