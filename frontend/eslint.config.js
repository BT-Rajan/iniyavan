import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import hooks from 'eslint-plugin-react-hooks'

export default [
  {ignores: ['dist']},
  {
    files: ['src/**/*.{js,jsx}', 'public/**/*.js', '*.config.js'],
    languageOptions: {ecmaVersion: 'latest', sourceType: 'module', globals: {...globals.browser, ...globals.serviceworker}, parserOptions: {ecmaFeatures: {jsx: true}}},
    plugins: {react, 'react-hooks': hooks},
    settings: {react: {version: 'detect'}},
    rules: {...js.configs.recommended.rules, 'react/jsx-no-undef': 'error', 'react/jsx-uses-vars': 'error', 'react/jsx-uses-react': 'error', 'react-hooks/rules-of-hooks': 'error'},
  },
]
