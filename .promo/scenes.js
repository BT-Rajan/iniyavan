// Zigora's promo: the Android app's own screens (PromoTest). Shots are the names capture.js saves; captions are keys in captions.js.
window.SCENES = [
  { type: 'logo', duration: 4.6, bg: 'ground', caption: 'tagline' },
  { type: 'phones', duration: 5.4, bg: 'accent', caption: 'signin', shots: ['signin'], alt: 'home', squares: true },
  { type: 'phones', duration: 5.8, bg: 'ground', caption: 'today', shots: ['home'], alt: 'course' },
  { type: 'phones', duration: 6.0, bg: 'accent', caption: 'gist', shots: ['topic', 'step'], reveal: true, squares: true },
  { type: 'phones', duration: 5.6, bg: 'ink', caption: 'check', shots: ['quiz', 'attempt'], squares: true },
  { type: 'phones', duration: 6.0, bg: 'pop', caption: 'mcq', shots: ['mcq-set', 'mcq-result'], reveal: true },
  { type: 'phones', duration: 5.8, bg: 'ground', caption: 'keep', shots: ['highlights', 'revision'] },
  { type: 'phones', duration: 5.4, bg: 'pop', caption: 'own', shots: ['build'], alt: 'progress' },
  { type: 'phones', duration: 5.8, bg: 'accent', caption: 'lang', shots: ['home-ta', 'topic-ar'], squares: true },
  { type: 'end', duration: 6.2, bg: 'ground', caption: 'endLine' },
];
