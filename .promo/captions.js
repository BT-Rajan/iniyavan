// Every line in Zigora's promo, per language. The first language in PROMO_LANGS is each scene's headline, the others the lines under
// it. The tone is the site's: calm and curious, never pushy. Tamil and Arabic lines reuse the site's own wording where it says the same
// thing; have a native speaker check the rest before publishing.
window.LANGUAGES = {
  en: { name: 'English', dir: 'ltr', font: 'Instrument Sans', weight: 700, lineHeight: 1.05 },
  ta: { name: 'Tamil', dir: 'ltr', font: 'Noto Sans Tamil', weight: 600, size: 0.62, lineHeight: 1.45 },
  ar: { name: 'Arabic', dir: 'rtl', font: 'Noto Sans Arabic', weight: 600, size: 0.8, lineHeight: 1.5 },
};

window.CAPTIONS = {
  en: {
    tagline: 'Learn your syllabus\nin short, curious steps.',
    signin: 'Sign in with Google.\nOne tap, and you\'re in.',
    today: 'One calm session\na day.',
    gist: 'A 30-second gist.\nThen go as deep\nas you like.',
    check: 'Check yourself.\nNo pressure.',
    mcq: 'Practice sets.\nSee what to revise.',
    keep: 'Highlight it.\nKeep it.\nRevise from it.',
    own: 'Bring your\nown notes too.',
    lang: 'In English, Tamil\nand Arabic.',
    endLine: 'Zigora Intelligence\nfor Android.',
    byline: 'AN APP BY',
    chips: ['SIGN IN', 'TODAY', 'LEARN', 'CHECK', 'PRACTICE', 'KEEP', 'YOUR NOTES', 'YOUR LANGUAGE'],
  },
  ta: {
    tagline: 'உங்கள் பாடத்திட்டத்தை\nசிறிய, ஆர்வமூட்டும் படிகளில்.',
    signin: 'Google மூலம் உள்நுழையுங்கள்.\nஒரே தட்டலில்.',
    today: 'நாளுக்கு ஒரு\nஅமைதியான அமர்வு.',
    gist: '30 வினாடிச் சுருக்கம்.\nவிரும்பும் அளவு ஆழமாக.',
    check: 'உங்களைச் சோதியுங்கள்.\nஅழுத்தம் இல்லை.',
    mcq: 'பயிற்சித் தொகுப்புகள்.\nஎதை மறுபார்வை செய்வது எனப் பாருங்கள்.',
    keep: 'சிறப்பியுங்கள்.\nவைத்திருங்கள்.\nமறுபார்வை செய்யுங்கள்.',
    own: 'உங்கள் சொந்தக்\nகுறிப்புகளும்.',
    lang: 'ஆங்கிலம், தமிழ்,\nஅரபு மொழிகளில்.',
    endLine: 'ஆண்ட்ராய்டுக்கான\nஜிகோரா இன்டெலிஜென்ஸ்.',
    byline: 'உருவாக்கியது',
    chips: ['உள்நுழைய', 'இன்று', 'கற்க', 'சோதிக்க', 'பயிற்சி', 'சேமிக்க', 'உங்கள் குறிப்புகள்', 'உங்கள் மொழி'],
  },
  ar: {
    tagline: 'تعلّم منهجك في\nخطوات قصيرة ومثيرة للفضول.',
    signin: 'سجّل الدخول عبر Google.\nبلمسة واحدة.',
    today: 'جلسة هادئة\nواحدة كل يوم.',
    gist: 'خلاصة في ٣٠ ثانية.\nثم تعمّق كما تشاء.',
    check: 'اختبر نفسك.\nبلا ضغط.',
    mcq: 'مجموعات تدريب.\nواعرف ما تحتاج مراجعته.',
    keep: 'ظلّل. احتفظ.\nراجع.',
    own: 'وملاحظاتك\nالخاصة أيضًا.',
    lang: 'بالإنجليزية والتاميلية\nوالعربية.',
    endLine: 'زيغورا إنتليجنس\nلأندرويد.',
    byline: 'تطبيق من',
    chips: ['الدخول', 'اليوم', 'تعلّم', 'اختبر', 'تدرّب', 'احتفظ', 'ملاحظاتك', 'لغتك'],
  },
};
