// PolarisGate v2.2 — AI Content Safety Gateway
const API = 'http://localhost:8002';

const T = {
  en: {
    brand: 'PolarisGate',
    subtitle: 'AI Governance & Runtime Control',
    email: 'Email',
    password: 'Password',
    login: 'Login',
    loginErr: 'Invalid email or password.',
    loggingIn: 'Logging in...',
    loginSuccess: 'Logged in successfully',
    logout: 'Logout',
    dashboard: 'Dashboard',
    overview: 'Overview',
    incidents: 'Incidents',
    models: 'Models',
    policies: 'Policies',
    policyRules: 'Policy Rules',
    testContent: 'Test Content',
    domains: 'Domains',
    blocklist: 'Blocklist',
    compliance: 'Compliance',
    auditLogs: 'Audit Logs',
    hallucination: 'Hallucination',
    settings: 'Settings',
    general: 'General',
    apiKeys: 'API Keys',
    webhooks: 'Webhooks',
    users: 'Users',
    traces24h: 'Traces (24h)',
    toxicityFlagged: 'Toxicity Flagged',
    piiDetected: 'PII Detected',
    blockedWords: 'Blocked Words',
    activeModels: 'Active Models',
    safetyScore: 'Safety Score',
    hallucinationRate: 'Hallucination Rate',
    recentIncidents: 'Recent Incidents',
    traceId: 'Trace ID',
    verdict: 'Verdict',
    reason: 'Reason',
    time: 'Time',
    score: 'Score',
    noIncidents: 'No incidents detected',
    noIncidentsFound: 'No incidents found',
    noData: 'Gateway healthy — no trace data yet.',
    monitoredModels: 'Monitored Models',
    modelsDesc: 'AI models sending content through PolarisGate for safety checking.',
    noModels: 'No models monitored yet',
    contentSafetyPolicies: 'Content Safety Policies',
    policyDesc: 'Configure how PolarisGate handles toxic content and PII in AI outputs.',
    saveChanges: 'Save Changes',
    policyName: 'Policy',
    type: 'Type',
    action: 'Action',
    severity: 'Severity',
    enabled: 'Enabled',
    policiesSaved: 'Policies saved',
    saveFailed: 'Save failed',
    testContentSafety: 'Test Content Safety',
    testDesc: 'Enter text to analyze for toxicity and PII. PII will be automatically redacted.',
    runAnalysis: 'Run Analysis',
    batchTest: 'Batch Test',
    analyzing: 'Analyzing...',
    analysisResults: 'Analysis Results',
    toxicContent: 'Toxic Content',
    detected: 'Detected',
    clean: 'Clean',
    confidenceScore: 'Confidence Score',
    piiDetectedLabel: 'PII Detected',
    yes: 'Yes',
    no: 'No',
    noneFound: 'None Found',
    promptInjection: 'Prompt Injection',
    detectedScore: 'Detected',
    noneDetected: 'None Detected',
    blocklistedLabel: 'Blocklisted',
    blockedYes: 'Yes — Blocked',
    piiTypesFound: 'PII Types Found',
    redactedOutput: 'Redacted Output',
    unavailable: 'Analysis service unavailable.',
    batchResults: 'Batch Results',
    tested: 'tested',
    domainThresholds: 'Domain Safety Thresholds',
    domainDesc: 'Set per-domain severity levels and actions for toxicity and PII detection.',
    saveDomainThresholds: 'Save Domain Thresholds',
    domainSaved: 'Domain thresholds saved',
    customBlocklist: 'Custom Blocklist',
    blocklistDesc: 'Add custom words or phrases to block. Content containing these words will be blocked.',
    addWord: 'Add Word',
    remove: 'Remove',
    noBlockedWords: 'No blocked words yet',
    wordAdded: 'Word added to blocklist',
    wordRemoved: 'Word removed',
    auditDesc: 'Complete record of all content safety decisions, policy changes, and login events.',
    noAuditLogs: 'No audit logs yet',
    hallucinationDetections: 'Hallucination Detections',
    hallucinationDesc: 'AI content flagged for factual inaccuracies by dual-model NLI detector.',
    noHallucinations: 'No hallucination detections yet',
    userManagement: 'User Management',
    userDesc: 'Manage users with role-based access: Admin (full), Safety Officer (test + policies), Viewer (read-only).',
    createUser: 'Create User',
    deactivate: 'Deactivate',
    inactive: 'Inactive',
    userCreated: 'User created',
    userDeactivated: 'User deactivated',
    emailPwRequired: 'Email and password required',
    saveSettings: 'Save Settings',
    settingsSaved: 'Settings saved',
    createNewKey: 'Create New Key',
    noApiKeys: 'No API keys created',
    keyCreated: 'Key Created — Copy Now!',
    keyWarning: 'This key will NOT be shown again.',
    keyRevoked: 'Key revoked',
    webhookSettings: 'Webhook Settings',
    webhookDesc: 'Get real-time notifications when safety incidents are detected.',
    webhookUrl: 'Webhook URL',
    events: 'Events (comma-separated)',
    saveWebhook: 'Save Webhook',
    webhookSaved: 'Webhook saved',
    comingSoon: 'Coming soon.',
    error: 'Error',
    all: 'All',
    toxic: 'Toxic',
    pii: 'PII',
    blocked: 'Blocked',
    never: 'Never',
    blockedVerdict: 'Blocked',
    toxicVerdict: 'Toxic',
    piiVerdict: 'PII',
    cleanVerdict: 'Clean',
    nA: 'N/A',
    enterText: 'Enter text to test',
    enterTextFirst: 'Enter text first',
    testing: 'Testing',
    items: 'items...',
    batchFailed: 'Batch test failed.',
    settingsReq: 'Required to change password',
    leaveBlank: 'Leave blank to keep current',
    blocklistPlaceholder: 'Enter word or phrase to block...',
    userEmailPlaceholder: 'user@email.com',
    passwordPlaceholder: 'Password',
    role: 'Role',
    safetyOfficer: 'Safety Officer',
    admin: 'Admin',
    viewer: 'Viewer',
    status: 'Status',
    active: 'Active',
  },
  fr: {
    brand: 'PolarisGate',
    subtitle: 'Gouvernance IA & Contrôle d\'Exécution',
    email: 'Email',
    password: 'Mot de passe',
    login: 'Connexion',
    loginErr: 'Email ou mot de passe invalide.',
    loggingIn: 'Connexion en cours...',
    loginSuccess: 'Connecté avec succès',
    logout: 'Déconnexion',
    dashboard: 'Tableau de Bord',
    overview: 'Aperçu',
    incidents: 'Incidents',
    models: 'Modèles',
    policies: 'Politiques',
    policyRules: 'Règles de Sécurité',
    testContent: 'Tester le Contenu',
    domains: 'Domaines',
    blocklist: 'Liste de Blocage',
    compliance: 'Conformité',
    auditLogs: 'Journaux d\'Audit',
    hallucination: 'Hallucination',
    settings: 'Paramètres',
    general: 'Général',
    apiKeys: 'Clés API',
    webhooks: 'Webhooks',
    users: 'Utilisateurs',
    traces24h: 'Traces (24h)',
    toxicityFlagged: 'Toxicité Signalée',
    piiDetected: 'DPI Détecté',
    blockedWords: 'Mots Bloqués',
    activeModels: 'Modèles Actifs',
    safetyScore: 'Score de Sécurité',
    hallucinationRate: 'Taux d\'Hallucination',
    recentIncidents: 'Incidents Récents',
    traceId: 'ID Trace',
    verdict: 'Verdict',
    reason: 'Raison',
    time: 'Heure',
    score: 'Score',
    noIncidents: 'Aucun incident détecté',
    noIncidentsFound: 'Aucun incident trouvé',
    noData: 'Passerelle saine — aucune donnée de trace.',
    monitoredModels: 'Modèles Surveillés',
    modelsDesc: 'Modèles IA envoyant du contenu via PolarisGate pour vérification de sécurité.',
    noModels: 'Aucun modèle surveillé',
    contentSafetyPolicies: 'Politiques de Sécurité du Contenu',
    policyDesc: 'Configurez comment PolarisGate gère le contenu toxique et les DPI dans les sorties IA.',
    saveChanges: 'Enregistrer',
    policyName: 'Politique',
    type: 'Type',
    action: 'Action',
    severity: 'Sévérité',
    enabled: 'Activé',
    policiesSaved: 'Politiques enregistrées',
    saveFailed: 'Échec de l\'enregistrement',
    testContentSafety: 'Tester la Sécurité du Contenu',
    testDesc: 'Saisissez du texte à analyser. Les DPI seront automatiquement masqués.',
    runAnalysis: 'Analyser',
    batchTest: 'Test par Lot',
    analyzing: 'Analyse en cours...',
    analysisResults: 'Résultats d\'Analyse',
    toxicContent: 'Contenu Toxique',
    detected: 'Détecté',
    clean: 'Propre',
    confidenceScore: 'Score de Confiance',
    piiDetectedLabel: 'DPI Détecté',
    yes: 'Oui',
    no: 'Non',
    noneFound: 'Aucun Trouvé',
    promptInjection: 'Injection de Requête',
    detectedScore: 'Détecté',
    noneDetected: 'Non Détecté',
    blocklistedLabel: 'Liste de Blocage',
    blockedYes: 'Oui — Bloqué',
    piiTypesFound: 'Types de DPI Trouvés',
    redactedOutput: 'Sortie Masquée',
    unavailable: 'Service d\'analyse indisponible.',
    batchResults: 'Résultats par Lot',
    tested: 'testé(s)',
    domainThresholds: 'Seuils de Sécurité par Domaine',
    domainDesc: 'Définissez les niveaux de sévérité et actions par domaine.',
    saveDomainThresholds: 'Enregistrer les Seuils',
    domainSaved: 'Seuils de domaine enregistrés',
    customBlocklist: 'Liste de Blocage Personnalisée',
    blocklistDesc: 'Ajoutez des mots à bloquer. Le contenu contenant ces mots sera bloqué.',
    addWord: 'Ajouter',
    remove: 'Supprimer',
    noBlockedWords: 'Aucun mot bloqué',
    wordAdded: 'Mot ajouté à la liste',
    wordRemoved: 'Mot supprimé',
    auditDesc: 'Registre complet des décisions de sécurité, changements de politique et connexions.',
    noAuditLogs: 'Aucun journal d\'audit',
    hallucinationDetections: 'Détections d\'Hallucination',
    hallucinationDesc: 'Contenu IA signalé pour inexactitudes factuelles.',
    noHallucinations: 'Aucune détection d\'hallucination',
    userManagement: 'Gestion des Utilisateurs',
    userDesc: 'Gérez les utilisateurs avec accès basé sur les rôles.',
    createUser: 'Créer Utilisateur',
    deactivate: 'Désactiver',
    inactive: 'Inactif',
    userCreated: 'Utilisateur créé',
    userDeactivated: 'Utilisateur désactivé',
    emailPwRequired: 'Email et mot de passe requis',
    saveSettings: 'Enregistrer',
    settingsSaved: 'Paramètres enregistrés',
    createNewKey: 'Créer Nouvelle Clé',
    noApiKeys: 'Aucune clé API créée',
    keyCreated: 'Clé Créée — Copiez Maintenant!',
    keyWarning: 'Cette clé ne sera PLUS affichée.',
    keyRevoked: 'Clé révoquée',
    webhookSettings: 'Paramètres Webhook',
    webhookDesc: 'Recevez des notifications en temps réel.',
    webhookUrl: 'URL Webhook',
    events: 'Événements (séparés par des virgules)',
    saveWebhook: 'Enregistrer',
    webhookSaved: 'Webhook enregistré',
    comingSoon: 'Bientôt disponible.',
    error: 'Erreur',
    all: 'Tous',
    toxic: 'Toxique',
    pii: 'DPI',
    blocked: 'Bloqué',
    never: 'Jamais',
    blockedVerdict: 'Bloqué',
    toxicVerdict: 'Toxique',
    piiVerdict: 'DPI',
    cleanVerdict: 'Propre',
    nA: 'N/D',
    enterText: 'Saisissez du texte à tester',
    enterTextFirst: 'Saisissez d\'abord du texte',
    testing: 'Test de',
    items: 'éléments...',
    batchFailed: 'Échec du test par lot.',
    settingsReq: 'Requis pour changer le mot de passe',
    leaveBlank: 'Laisser vide pour conserver',
    blocklistPlaceholder: 'Saisissez un mot à bloquer...',
    userEmailPlaceholder: 'utilisateur@email.com',
    passwordPlaceholder: 'Mot de passe',
    role: 'Rôle',
    safetyOfficer: 'Agent de Sécurité',
    admin: 'Admin',
    viewer: 'Observateur',
    status: 'Statut',
    active: 'Actif',
  },
  ar: {
    brand: 'بولاريس جيت',
    subtitle: 'حوكمة الذكاء الاصطناعي والتحكم في وقت التشغيل',
    email: 'البريد الإلكتروني',
    password: 'كلمة المرور',
    login: 'تسجيل الدخول',
    loginErr: 'بريد إلكتروني أو كلمة مرور غير صالحة.',
    loggingIn: 'جاري تسجيل الدخول...',
    loginSuccess: 'تم تسجيل الدخول بنجاح',
    logout: 'تسجيل الخروج',
    dashboard: 'لوحة التحكم',
    overview: 'نظرة عامة',
    incidents: 'الحوادث',
    models: 'النماذج',
    policies: 'السياسات',
    policyRules: 'قواعد السلامة',
    testContent: 'اختبار المحتوى',
    domains: 'المجالات',
    blocklist: 'قائمة الحظر',
    compliance: 'الامتثال',
    auditLogs: 'سجلات التدقيق',
    hallucination: 'الهلوسة',
    settings: 'الإعدادات',
    general: 'عام',
    apiKeys: 'مفاتيح API',
    webhooks: 'Webhooks',
    users: 'المستخدمين',
    traces24h: 'الآثار (24 ساعة)',
    toxicityFlagged: 'إشارات السمية',
    piiDetected: 'اكتشاف المعلومات الشخصية',
    blockedWords: 'الكلمات المحظورة',
    activeModels: 'النماذج النشطة',
    safetyScore: 'درجة السلامة',
    hallucinationRate: 'معدل الهلوسة',
    recentIncidents: 'الحوادث الأخيرة',
    traceId: 'معرف الأثر',
    verdict: 'الحكم',
    reason: 'السبب',
    time: 'الوقت',
    score: 'النتيجة',
    noIncidents: 'لم يتم اكتشاف أي حوادث',
    noIncidentsFound: 'لم يتم العثور على حوادث',
    noData: 'البوابة تعمل - لا توجد بيانات أثر بعد.',
    monitoredModels: 'النماذج المراقبة',
    modelsDesc: 'نماذج الذكاء الاصطناعي التي ترسل المحتوى عبر PolarisGate للتحقق من السلامة.',
    noModels: 'لا توجد نماذج مراقبة بعد',
    contentSafetyPolicies: 'سياسات سلامة المحتوى',
    policyDesc: 'تكوين كيفية تعامل PolarisGate مع المحتوى السام والمعلومات الشخصية في مخرجات الذكاء الاصطناعي.',
    saveChanges: 'حفظ التغييرات',
    policyName: 'السياسة',
    type: 'النوع',
    action: 'الإجراء',
    severity: 'الخطورة',
    enabled: 'مفعل',
    policiesSaved: 'تم حفظ السياسات',
    saveFailed: 'فشل الحفظ',
    testContentSafety: 'اختبار سلامة المحتوى',
    testDesc: 'أدخل النص للتحليل. سيتم إخفاء المعلومات الشخصية تلقائياً.',
    runAnalysis: 'تشغيل التحليل',
    batchTest: 'اختبار بالدفعات',
    analyzing: 'جاري التحليل...',
    analysisResults: 'نتائج التحليل',
    toxicContent: 'محتوى سام',
    detected: 'مكتشف',
    clean: 'نظيف',
    confidenceScore: 'درجة الثقة',
    piiDetectedLabel: 'اكتشاف المعلومات الشخصية',
    yes: 'نعم',
    no: 'لا',
    noneFound: 'لم يتم العثور',
    promptInjection: 'حقن الطلب',
    detectedScore: 'مكتشف',
    noneDetected: 'غير مكتشف',
    blocklistedLabel: 'قائمة الحظر',
    blockedYes: 'نعم - محظور',
    piiTypesFound: 'أنواع المعلومات الشخصية المكتشفة',
    redactedOutput: 'الناتج المحمي',
    unavailable: 'خدمة التحليل غير متاحة.',
    batchResults: 'نتائج الدفعات',
    tested: 'تم الاختبار',
    domainThresholds: 'عتبات السلامة حسب المجال',
    domainDesc: 'تحديد مستويات الخطورة والإجراءات لكل مجال.',
    saveDomainThresholds: 'حفظ العتبات',
    domainSaved: 'تم حفظ عتبات المجال',
    customBlocklist: 'قائمة الحظر المخصصة',
    blocklistDesc: 'أضف كلمات للحظر. المحتوى الذي يحتوي على هذه الكلمات سيتم حظره.',
    addWord: 'إضافة كلمة',
    remove: 'إزالة',
    noBlockedWords: 'لا توجد كلمات محظورة',
    wordAdded: 'تمت إضافة الكلمة إلى القائمة',
    wordRemoved: 'تمت إزالة الكلمة',
    auditDesc: 'سجل كامل لقرارات سلامة المحتوى وتغييرات السياسات وأحداث تسجيل الدخول.',
    noAuditLogs: 'لا توجد سجلات تدقيق',
    hallucinationDetections: 'اكتشافات الهلوسة',
    hallucinationDesc: 'محتوى الذكاء الاصطناعي الذي تم الإبلاغ عنه لعدم الدقة الواقعية.',
    noHallucinations: 'لا توجد اكتشافات هلوسة',
    userManagement: 'إدارة المستخدمين',
    userDesc: 'إدارة المستخدمين مع وصول قائم على الأدوار.',
    createUser: 'إنشاء مستخدم',
    deactivate: 'تعطيل',
    inactive: 'غير نشط',
    userCreated: 'تم إنشاء المستخدم',
    userDeactivated: 'تم تعطيل المستخدم',
    emailPwRequired: 'البريد الإلكتروني وكلمة المرور مطلوبان',
    saveSettings: 'حفظ الإعدادات',
    settingsSaved: 'تم حفظ الإعدادات',
    createNewKey: 'إنشاء مفتاح جديد',
    noApiKeys: 'لم يتم إنشاء مفاتيح API',
    keyCreated: 'تم إنشاء المفتاح - انسخه الآن!',
    keyWarning: 'لن يتم عرض هذا المفتاح مرة أخرى.',
    keyRevoked: 'تم إلغاء المفتاح',
    webhookSettings: 'إعدادات Webhook',
    webhookDesc: 'تلقي إشعارات في الوقت الفعلي.',
    webhookUrl: 'رابط Webhook',
    events: 'الأحداث (مفصولة بفواصل)',
    saveWebhook: 'حفظ',
    webhookSaved: 'تم حفظ Webhook',
    comingSoon: 'قريباً.',
    error: 'خطأ',
    all: 'الكل',
    toxic: 'سام',
    pii: 'معلومات شخصية',
    blocked: 'محظور',
    never: 'أبداً',
    blockedVerdict: 'محظور',
    toxicVerdict: 'سام',
    piiVerdict: 'معلومات شخصية',
    cleanVerdict: 'نظيف',
    nA: 'غير متاح',
    enterText: 'أدخل النص للاختبار',
    enterTextFirst: 'أدخل النص أولاً',
    testing: 'اختبار',
    items: 'عناصر...',
    batchFailed: 'فشل الاختبار بالدفعات.',
    settingsReq: 'مطلوب لتغيير كلمة المرور',
    leaveBlank: 'اتركه فارغاً للاحتفاظ بالحالي',
    blocklistPlaceholder: 'أدخل كلمة للحظر...',
    userEmailPlaceholder: 'مستخدم@بريد.com',
    passwordPlaceholder: 'كلمة المرور',
    role: 'الدور',
    safetyOfficer: 'مسؤول السلامة',
    admin: 'مدير',
    viewer: 'مشاهد',
    status: 'الحالة',
    active: 'نشط',
    language: 'اللغة',
    langEN: 'English',
    langFR: 'Français',
    langAR: 'العربية',
  }
};

let lang = localStorage.getItem('polarisgate-lang') || 'en';
function t(key) { return (T[lang] && T[lang][key]) || (T.en[key] || key); }

function showToast(msg, type) {
  const c = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; }, 3000);
  setTimeout(() => el.remove(), 3300);
}

function setLang(l) {
  lang = l;
  localStorage.setItem('polarisgate-lang', lang);
  render();
}

const state = { tab: 'dashboard', sub: 'overview', _filter: null };
let token = null;
function setTab(t, s) { state.tab = t; state.sub = s || 'overview'; if (t !== 'dashboard' || s !== 'incidents') state._filter = null; render(); }

async function handleLogin() {
  const email = document.getElementById('login-email').value;
  const pw = document.getElementById('login-password').value;
  const btn = document.getElementById('login-btn');
  const err = document.getElementById('login-error');
  btn.disabled = true; btn.textContent = t('loggingIn'); err.textContent = '';
  try {
    const fd = new URLSearchParams(); fd.append('username', email); fd.append('password', pw);
    const res = await fetch(API + '/auth/token', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: fd });
    if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.detail || 'Login failed'); }
    const json = await res.json(); token = json.access_token;
    localStorage.setItem('polarisgate-token', token);
    showToast(t('loginSuccess'), 'success');
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('dashboard-screen').classList.remove('hidden');
    render();
  } catch (e) { err.textContent = e.message === 'Invalid credentials' ? t('loginErr') : e.message; }
  finally { btn.disabled = false; btn.textContent = t('login'); }
}

function handleLogout() {
  token = null; localStorage.removeItem('polarisgate-token');
  document.getElementById('login-screen').classList.remove('hidden');
  document.getElementById('dashboard-screen').classList.add('hidden');
}
document.getElementById('login-password').addEventListener('keydown', (e) => { if (e.key === 'Enter') handleLogin(); });

async function get(endpoint) {
  try { const r = await fetch(API + endpoint, { headers: { Authorization: 'Bearer ' + token } }); if (!r.ok) return null; return r.json(); } catch (e) { return null; }
}
async function post(endpoint, body) {
  try {
    const r = await fetch(API + endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token }, body: JSON.stringify(body) });
    if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(j.detail || 'Request failed'); }
    return r.json();
  } catch (e) { showToast(e.message, 'error'); return null; }
}
async function del(endpoint) {
  try { await fetch(API + endpoint, { method: 'DELETE', headers: { Authorization: 'Bearer ' + token } }); return true; } catch (e) { return false; }
}

async function render() {
  if (!token) { token = localStorage.getItem('polarisgate-token'); if (!token) return; document.getElementById('login-screen').classList.add('hidden'); document.getElementById('dashboard-screen').classList.remove('hidden'); }

  const tabs = [
    { k: 'dashboard', l: t('dashboard') }, { k: 'policy', l: t('policies') },
    { k: 'compliance', l: t('compliance') }, { k: 'admin', l: t('settings') }
  ];
  document.getElementById('main-tabs').innerHTML = tabs.map(tb => '<button class="tab' + (state.tab === tb.k ? ' active' : '') + '" onclick="setTab(\'' + tb.k + '\')">' + tb.l + '</button>').join('');

  const subTabs = {
    dashboard: [{ k: 'overview', l: t('overview') }, { k: 'incidents', l: t('incidents') }, { k: 'models', l: t('models') }],
    policy: [{ k: 'guardrails', l: t('policyRules') }, { k: 'testing', l: t('testContent') }, { k: 'thresholds', l: t('domains') }, { k: 'blocklist', l: t('blocklist') }],
    compliance: [{ k: 'audit', l: t('auditLogs') }, { k: 'hallucination', l: t('hallucination') }],
    admin: [{ k: 'settings', l: t('general') }, { k: 'apikeys', l: t('apiKeys') }, { k: 'webhooks', l: t('webhooks') }, { k: 'users', l: t('users') }]
  };
  const st = subTabs[state.tab] || [];
  document.getElementById('sidebar').innerHTML = st.map(s => '<button class="sidebar-btn' + (state.sub === s.k ? ' active' : '') + '" onclick="setTab(\'' + state.tab + '\',\'' + s.k + '\')">' + s.l + '</button>').join('');
  const main = document.getElementById('main-content');
  main.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';

  try {
    if (state.tab === 'dashboard') {
      if (state.sub === 'overview') await renderDashboard();
      else if (state.sub === 'incidents') await renderIncidents();
      else if (state.sub === 'models') await renderModels();
    } else if (state.tab === 'policy') {
      if (state.sub === 'testing') await renderPolicyTest();
      else if (state.sub === 'thresholds') await renderDomainThresholds();
      else if (state.sub === 'blocklist') await renderBlocklist();
      else await renderPolicyGuardrails();
    } else if (state.tab === 'compliance') {
      if (state.sub === 'hallucination') await renderHallucination();
      else await renderAuditLogs();
    } else if (state.tab === 'admin') {
      if (state.sub === 'apikeys') await renderApiKeys();
      else if (state.sub === 'webhooks') await renderWebhooks();
      else if (state.sub === 'users') await renderUsers();
      else await renderSettings();
    } else main.innerHTML = '<div class="card"><h2>' + state.tab + '</h2><p style="color:#94A3B8">' + t('comingSoon') + '</p></div>';
  } catch (e) { main.innerHTML = '<div class="card"><h2>' + t('error') + '</h2><p style="color:#ef4444">' + e.message + '</p></div>'; }
}

async function renderDashboard() {
  const s = await get('/api/v1/dashboard/summary');
  const incidents = await get('/api/v1/dashboard/incidents?limit=5');
  const h = await get('/api/v1/hallucination/trend');
  var hallRate = t('nA');
  if (h && h.points && h.points.length) {
    var total = 0; h.points.forEach(function(p) { total += p.score || 0; });
    hallRate = (total / h.points.length).toFixed(1);
  } else {
    var det = await get('/api/v1/hallucination/detections?limit=100');
    if (det && det.detections && det.detections.length) hallRate = det.detections.length + ' total';
  }
  if (!s) { document.getElementById('main-content').innerHTML = '<div class="card"><h2>' + t('overview') + '</h2><p style="color:#94A3B8">' + t('noData') + '</p></div>'; return; }
  document.getElementById('main-content').innerHTML =
    '<div class="summary-grid">' +
      '<div class="summary-card" onclick="setTab(\'dashboard\',\'incidents\')"><div class="label">' + t('traces24h') + '</div><div class="value">' + (s.total_traces_last_24h || 0) + '</div></div>' +
      '<div class="summary-card" onclick="state._filter=\'toxic\';setTab(\'dashboard\',\'incidents\')"><div class="label">' + t('toxicityFlagged') + '</div><div class="value" style="color:' + (s.flagged_toxicity > 0 ? '#ef4444' : '#4F8EF7') + '">' + (s.flagged_toxicity || 0) + '</div></div>' +
      '<div class="summary-card" onclick="state._filter=\'pii\';setTab(\'dashboard\',\'incidents\')"><div class="label">' + t('piiDetected') + '</div><div class="value" style="color:' + (s.pii_leaks > 0 ? '#f59e0b' : '#4F8EF7') + '">' + (s.pii_leaks || 0) + '</div></div>' +
      '<div class="summary-card" onclick="setTab(\'dashboard\',\'models\')"><div class="label">' + t('activeModels') + '</div><div class="value">' + (s.active_models || 0) + '</div></div>' +
      '<div class="summary-card" onclick="state._filter=\'blocked\';setTab(\'dashboard\',\'incidents\')"><div class="label">' + t('blockedWords') + '</div><div class="value" style="color:' + ((s.blocked_count || 0) > 0 ? '#ef4444' : '#4F8EF7') + '">' + (s.blocked_count || 0) + '</div></div>' +
      '<div class="summary-card"><div class="label">' + t('safetyScore') + '</div><div class="value">' + (typeof s.fairness_score === 'number' ? (s.fairness_score * 100).toFixed(1) + '%' : (s.fairness_score || t('nA'))) + '</div></div>' +
      '<div class="summary-card" onclick="setTab(\'compliance\',\'hallucination\')"><div class="label">' + t('hallucinationRate') + '</div><div class="value" style="color:' + (hallRate !== t('nA') ? '#4F8EF7' : '#f59e0b') + '">' + hallRate + '</div></div>' +
    '</div>' +
    '<div class="card"><h2>' + t('recentIncidents') + '</h2>' +
      '<table><thead><tr><th>' + t('traceId') + '</th><th>' + t('verdict') + '</th><th>' + t('reason') + '</th><th>' + t('time') + '</th></tr></thead>' +
      '<tbody>' + ((incidents || []).map(function(i) { var badge = ''; if (i.blocklisted) badge = '<span class="badge badge-toxic">' + t('blockedVerdict') + '</span>'; else if (i.toxic) badge = '<span class="badge badge-toxic">' + t('toxicVerdict') + '</span>'; else if (i.pii_detected) badge = '<span class="badge badge-pii">' + t('piiVerdict') + '</span>'; else badge = '<span class="badge badge-safe">' + t('cleanVerdict') + '</span>'; return '<tr><td style="font-family:monospace;font-size:12px">' + (i.trace_id || '').toString().slice(0, 8) + '...</td><td>' + badge + '</td><td>' + (i.reason || '') + '</td><td style="font-size:12px;color:#94A3B8">' + (i.timestamp || '') + '</td></tr>'; }).join('') || '<tr><td colspan="4" style="color:#94A3B8">' + t('noIncidents') + '</td></tr>') + '</tbody>' +
      '</table></div>';
}

async function renderIncidents() {
  const incidents = await get('/api/v1/dashboard/incidents?limit=30');
  const items = incidents || [];
  const flt = state._filter;
  const filtered = flt ? items.filter(function(i) { return flt === 'toxic' ? i.toxic : flt === 'pii' ? i.pii_detected : i.blocklisted; }) : items;
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('incidents') + '</h2>' +
      '<div class="filter-bar"><button class="filter-btn' + (!flt ? ' active' : '') + '" onclick="state._filter=null;render()">' + t('all') + '</button><button class="filter-btn' + (flt === 'toxic' ? ' active' : '') + '" onclick="state._filter=\'toxic\';render()">' + t('toxic') + '</button><button class="filter-btn' + (flt === 'pii' ? ' active' : '') + '" onclick="state._filter=\'pii\';render()">' + t('pii') + '</button><button class="filter-btn' + (flt === 'blocked' ? ' active' : '') + '" onclick="state._filter=\'blocked\';render()">' + t('blocked') + '</button></div>' +
      '<table><thead><tr><th>' + t('traceId') + '</th><th>' + t('verdict') + '</th><th>' + t('score') + '</th><th>' + t('reason') + '</th><th>' + t('time') + '</th></tr></thead>' +
      '<tbody>' + (filtered.map(function(i) { var badge = ''; if (i.blocklisted) badge = '<span class="badge badge-toxic">' + t('blockedVerdict') + '</span>'; else if (i.toxic) badge = '<span class="badge badge-toxic">' + t('toxicVerdict') + '</span>'; else if (i.pii_detected) badge = '<span class="badge badge-pii">' + t('piiVerdict') + '</span>'; else badge = '<span class="badge badge-safe">' + t('cleanVerdict') + '</span>'; return '<tr><td style="font-family:monospace;font-size:12px">' + (i.trace_id || '').toString().slice(0, 8) + '...</td><td>' + badge + '</td><td>' + (i.toxic_score != null ? i.toxic_score : '-') + '</td><td>' + (i.reason || '') + '</td><td style="font-size:12px;color:#94A3B8">' + (i.timestamp || '') + '</td></tr>'; }).join('') || '<tr><td colspan="5" style="color:#94A3B8">' + t('noIncidentsFound') + '</td></tr>') + '</tbody></table></div>';
}

async function renderModels() {
  const models = await get('/api/v1/dashboard/models');
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('monitoredModels') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + t('modelsDesc') + '</p>' +
      '<table><thead><tr><th>' + t('modelId') + '</th><th>' + t('traceCount') + '</th><th>' + t('lastSeen') + '</th></tr></thead>' +
      '<tbody>' + ((models || []).map(function(m) { return '<tr><td>' + m.model_id + '</td><td>' + (m.trace_count || 0) + '</td><td>' + (m.last_seen || t('never')) + '</td></tr>'; }).join('') || '<tr><td colspan="3" style="color:#94A3B8">' + t('noModels') + '</td></tr>') + '</tbody></table></div>';
}

var policyEdits = [];
async function renderPolicyGuardrails() {
  const policies = await get('/api/v1/policies');
  const items = policies ? policies.policies : [];
  policyEdits = items.map(function(p) { return Object.assign({}, p); });
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('contentSafetyPolicies') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + t('policyDesc') + '</p>' +
      '<button class="btn-primary" onclick="savePolicies()" style="width:auto;padding:8px 20px;margin-bottom:16px">' + t('saveChanges') + '</button>' +
      '<table><thead><tr><th>' + t('policyName') + '</th><th>' + t('type') + '</th><th>' + t('action') + '</th><th>' + t('severity') + '</th><th>' + t('enabled') + '</th></tr></thead>' +
      '<tbody>' + policyEdits.map(function(p, i) {
        return '<tr><td>' + p.name + '</td><td>' + p.type + '</td><td><select onchange="policyEdits[' + i + '].action=this.value;rP()" style="padding:4px 8px;border-radius:8px;border:1px solid rgba(79,142,247,0.2);background:#0B1120;color:#E2E8F0;font-size:12px"><option value="block" ' + (p.action === 'block' ? 'selected' : '') + '>Block</option><option value="mask" ' + (p.action === 'mask' ? 'selected' : '') + '>Mask</option><option value="flag" ' + (p.action === 'flag' ? 'selected' : '') + '>Flag</option><option value="allow" ' + (p.action === 'allow' ? 'selected' : '') + '>Allow</option></select></td><td><select onchange="policyEdits[' + i + '].severity=this.value;rP()" style="padding:4px 8px;border-radius:8px;border:1px solid rgba(79,142,247,0.2);background:#0B1120;color:#E2E8F0;font-size:12px"><option value="critical" ' + (p.severity === 'critical' ? 'selected' : '') + '>Critical</option><option value="high" ' + (p.severity === 'high' ? 'selected' : '') + '>High</option><option value="medium" ' + (p.severity === 'medium' ? 'selected' : '') + '>Medium</option><option value="low" ' + (p.severity === 'low' ? 'selected' : '') + '>Low</option></select></td><td><label class="toggle"><input type="checkbox" ' + (p.enabled ? 'checked' : '') + ' onchange="policyEdits[' + i + '].enabled=this.checked;rP()"><span class="toggle-slider"></span></label></td></tr>';
      }).join('') + '</tbody></table></div>';
}
function rP() {
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('contentSafetyPolicies') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + t('policyDesc') + '</p>' +
      '<button class="btn-primary" onclick="savePolicies()" style="width:auto;padding:8px 20px;margin-bottom:16px">' + t('saveChanges') + '</button>' +
      '<table><thead><tr><th>' + t('policyName') + '</th><th>' + t('type') + '</th><th>' + t('action') + '</th><th>' + t('severity') + '</th><th>' + t('enabled') + '</th></tr></thead>' +
      '<tbody>' + policyEdits.map(function(p, i) {
        return '<tr><td>' + p.name + '</td><td>' + p.type + '</td><td><select onchange="policyEdits[' + i + '].action=this.value;rP()" style="padding:4px 8px;border-radius:8px;border:1px solid rgba(79,142,247,0.2);background:#0B1120;color:#E2E8F0;font-size:12px"><option value="block" ' + (p.action === 'block' ? 'selected' : '') + '>Block</option><option value="mask" ' + (p.action === 'mask' ? 'selected' : '') + '>Mask</option><option value="flag" ' + (p.action === 'flag' ? 'selected' : '') + '>Flag</option><option value="allow" ' + (p.action === 'allow' ? 'selected' : '') + '>Allow</option></select></td><td><select onchange="policyEdits[' + i + '].severity=this.value;rP()" style="padding:4px 8px;border-radius:8px;border:1px solid rgba(79,142,247,0.2);background:#0B1120;color:#E2E8F0;font-size:12px"><option value="critical" ' + (p.severity === 'critical' ? 'selected' : '') + '>Critical</option><option value="high" ' + (p.severity === 'high' ? 'selected' : '') + '>High</option><option value="medium" ' + (p.severity === 'medium' ? 'selected' : '') + '>Medium</option><option value="low" ' + (p.severity === 'low' ? 'selected' : '') + '>Low</option></select></td><td><label class="toggle"><input type="checkbox" ' + (p.enabled ? 'checked' : '') + ' onchange="policyEdits[' + i + '].enabled=this.checked;rP()"><span class="toggle-slider"></span></label></td></tr>';
      }).join('') + '</tbody></table></div>';
}
async function savePolicies() { const r = await post('/api/v1/policies', { policies: policyEdits }); showToast(r ? t('policiesSaved') : t('saveFailed'), r ? 'success' : 'error'); }
async function renderPolicyTest() {
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('testContentSafety') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + t('testDesc') + '</p>' +
      '<div class="form-group"><textarea id="test-text" style="width:100%;padding:12px;border-radius:12px;border:1px solid rgba(79,142,247,0.12);background:#0B1120;color:#E2E8F0;font-size:14px;resize:vertical;min-height:120px" placeholder="' + (lang === 'fr' ? 'Collez le contenu à analyser...' : 'Paste content to analyze...') + '"></textarea></div>' +
      '<div style="display:flex;gap:8px;margin-top:12px"><button class="btn-primary" onclick="runGuardrailTest()" id="test-btn" style="width:auto;padding:10px 24px">' + t('runAnalysis') + '</button><button class="btn-primary" onclick="runBatchTest()" id="batch-btn" style="width:auto;padding:10px 24px;background:linear-gradient(135deg,#7C8BB5,#4F8EF7)">' + t('batchTest') + '</button></div>' +
      '<div id="test-result" style="margin-top:16px"></div></div>';
}
async function runGuardrailTest() {
  var text = document.getElementById('test-text').value;
  if (!text) { showToast(t('enterText'), 'error'); return; }
  var btn = document.getElementById('test-btn'); btn.disabled = true; btn.textContent = t('analyzing');
  var result = await post('/api/v1/guardrails/check', { text: text });
  btn.disabled = false; btn.textContent = t('runAnalysis');
  var el = document.getElementById('test-result');
  if (!result) { el.innerHTML = '<p style="color:#ef4444">' + t('unavailable') + '</p>'; return; }
  el.innerHTML =
    '<div class="card" style="margin-top:16px"><h3>' + t('analysisResults') + '</h3>' +
      '<p><strong>' + t('toxicContent') + ':</strong> ' + (result.toxic ? '<span class="badge badge-toxic">' + t('detected') + '</span>' : '<span class="badge badge-safe">' + t('clean') + '</span>') + '</p>' +
      '<p><strong>' + t('confidenceScore') + ':</strong> ' + (result.toxic_score != null ? result.toxic_score : t('nA')) + '</p>' +
      (result.reason ? '<p><strong>' + t('reason') + ':</strong> ' + result.reason + '</p>' : '') +
      '<p><strong>' + t('piiDetectedLabel') + ':</strong> ' + (result.pii_detected ? '<span class="badge badge-pii">' + t('yes') + '</span>' : '<span class="badge badge-safe">' + t('noneFound') + '</span>') + '</p>' +
      '<p><strong>' + t('promptInjection') + ':</strong> ' + (result.injection_detected ? '<span class="badge badge-toxic">' + t('detected') + ' (' + (result.injection_score || 0).toFixed(2) + ')</span>' : '<span class="badge badge-safe">' + t('noneDetected') + '</span>') + '</p>' +
      '<p><strong>' + t('blocklistedLabel') + ':</strong> ' + (result.blocklisted ? '<span class="badge badge-toxic">' + t('blockedYes') + '</span>' : '<span class="badge badge-safe">' + t('noneFound') + '</span>') + '</p>' +
      (result.pii_types && result.pii_types.length ? '<p><strong>' + t('piiTypesFound') + ':</strong> ' + result.pii_types.join(', ') + '</p>' : '') +
      '<p style="margin-top:12px"><strong>' + t('redactedOutput') + ':</strong></p>' +
      '<div style="background:#0B1120;border:1px solid rgba(79,142,247,0.12);border-radius:8px;padding:12px;font-family:monospace;font-size:13px;color:#E2E8F0;white-space:pre-wrap;word-break:break-word">' + (result.redacted_text || text) + '</div>' +
    '</div>';
}
async function runBatchTest() {
  var text = document.getElementById('test-text').value;
  if (!text) { showToast(t('enterTextFirst'), 'error'); return; }
  var lines = text.split('\n').filter(function(l) { return l.trim(); });
  var btn = document.getElementById('batch-btn'); btn.disabled = true; btn.textContent = t('testing') + ' ' + lines.length + ' ' + t('items');
  var result = await post('/api/v1/guardrails/batch', { texts: lines });
  btn.disabled = false; btn.textContent = t('batchTest');
  var el = document.getElementById('test-result');
  if (!result) { el.innerHTML = '<p style="color:#ef4444">' + t('batchFailed') + '</p>'; return; }
  el.innerHTML =
    '<div class="card" style="margin-top:16px"><h3>' + t('batchResults') + ' (' + result.total + ' ' + t('tested') + ')</h3>' +
      '<table><thead><tr><th>#</th><th>Text</th><th>Toxic</th><th>PII</th></tr></thead>' +
      '<tbody>' + (result.results || []).map(function(r, i) { return '<tr><td>' + (i + 1) + '</td><td style="font-size:12px;max-width:300px;word-break:break-all">' + (lines[i] || '').slice(0, 60) + '...</td><td>' + (r.toxic ? '<span class="badge badge-toxic">' + t('yes') + '</span>' : '<span class="badge badge-safe">' + t('no') + '</span>') + '</td><td>' + (r.pii_detected ? '<span class="badge badge-pii">' + t('yes') + '</span>' : '<span class="badge badge-safe">' + t('no') + '</span>') + '</td></tr>'; }).join('') + '</tbody></table></div>';
}

async function renderDomainThresholds() {
  var dt = await get('/api/v1/settings/domain-thresholds');
  var thresholds = dt ? (dt.thresholds || []) : [];
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('domainThresholds') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + t('domainDesc') + '</p>' +
      '<div id="domain-list">' + thresholds.map(function(t, i) {
        return '<div style="display:flex;gap:8px;margin-bottom:8px;align-items:center"><span style="min-width:100px;font-size:13px;color:#94A3B8">' + t.domain + '</span><select id="dt-severity-' + i + '" style="padding:4px 8px;border-radius:8px;border:1px solid rgba(79,142,247,0.2);background:#0B1120;color:#E2E8F0;font-size:12px"><option value="critical" ' + (t.severity === 'critical' ? 'selected' : '') + '>Critical</option><option value="high" ' + (t.severity === 'high' ? 'selected' : '') + '>High</option><option value="medium" ' + (t.severity === 'medium' ? 'selected' : '') + '>Medium</option><option value="low" ' + (t.severity === 'low' ? 'selected' : '') + '>Low</option></select><select id="dt-tox-' + i + '" style="padding:4px 8px;border-radius:8px;border:1px solid rgba(79,142,247,0.2);background:#0B1120;color:#E2E8F0;font-size:12px"><option value="block" ' + (t.toxicity_action === 'block' ? 'selected' : '') + '>Tox: Block</option><option value="flag" ' + (t.toxicity_action === 'flag' ? 'selected' : '') + '>Tox: Flag</option><option value="allow" ' + (t.toxicity_action === 'allow' ? 'selected' : '') + '>Tox: Allow</option></select><select id="dt-pii-' + i + '" style="padding:4px 8px;border-radius:8px;border:1px solid rgba(79,142,247,0.2);background:#0B1120;color:#E2E8F0;font-size:12px"><option value="block" ' + (t.pii_action === 'block' ? 'selected' : '') + '>PII: Block</option><option value="mask" ' + (t.pii_action === 'mask' ? 'selected' : '') + '>PII: Mask</option><option value="flag" ' + (t.pii_action === 'flag' ? 'selected' : '') + '>PII: Flag</option></select></div>';
      }).join('') + '</div>' +
      '<button class="btn-primary" onclick="saveDomainThresholds()" style="width:auto;padding:10px 24px">' + t('saveDomainThresholds') + '</button></div>';
}
async function saveDomainThresholds() {
  var dt = await get('/api/v1/settings/domain-thresholds');
  var items = dt ? (dt.thresholds || []) : [];
  var updated = items.map(function(t, i) {
    return { domain: t.domain, severity: (document.getElementById('dt-severity-' + i) || {}).value || t.severity, toxicity_action: (document.getElementById('dt-tox-' + i) || {}).value || t.toxicity_action, pii_action: (document.getElementById('dt-pii-' + i) || {}).value || t.pii_action };
  });
  await post('/api/v1/settings/domain-thresholds', { thresholds: updated });
  showToast(t('domainSaved'), 'success');
}

async function renderBlocklist() {
  var bl = await get('/api/v1/settings/blocklist');
  var words = bl ? (bl.words || []) : [];
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('customBlocklist') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + t('blocklistDesc') + '</p>' +
      '<div style="display:flex;gap:8px;margin-bottom:16px"><input id="blocklist-word" style="flex:1;padding:10px 16px;border-radius:12px;border:1px solid rgba(79,142,247,0.12);background:#0B1120;color:#E2E8F0;font-size:14px" placeholder="' + t('blocklistPlaceholder') + '" onkeydown="if(event.key===\'Enter\')addBlocklistWord()"/><button class="btn-primary" onclick="addBlocklistWord()" style="width:auto;padding:10px 20px;margin-top:0">' + t('addWord') + '</button></div>' +
      '<table><thead><tr><th>Word</th><th>Action</th></tr></thead>' +
      '<tbody>' + (words.length ? words.map(function(w) { return '<tr><td>' + w + '</td><td><button class="filter-btn" onclick="removeBlocklistWord(\'' + w + '\')">' + t('remove') + '</button></td></tr>'; }).join('') : '<tr><td colspan="2" style="color:#94A3B8">' + t('noBlockedWords') + '</td></tr>') + '</tbody></table></div>';
}
async function addBlocklistWord() {
  var word = document.getElementById('blocklist-word').value.trim();
  if (!word) return;
  var result = await post('/api/v1/settings/blocklist', { word: word });
  if (result) { document.getElementById('blocklist-word').value = ''; renderBlocklist(); showToast(t('wordAdded'), 'success'); }
}
async function removeBlocklistWord(word) { await del('/api/v1/settings/blocklist/' + encodeURIComponent(word)); renderBlocklist(); showToast(t('wordRemoved'), 'success'); }

async function renderAuditLogs() {
  var logs = await get('/api/v1/audit?limit=50');
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('auditLogs') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + t('auditDesc') + '</p>' +
      '<table><thead><tr><th>User</th><th>Action</th><th>Resource</th><th>' + t('time') + '</th></tr></thead>' +
      '<tbody>' + ((logs || []).map(function(l) { return '<tr><td>' + (l.user_email || '') + '</td><td>' + l.action + '</td><td>' + (l.resource_type || '') + '</td><td style="font-size:12px;color:#94A3B8">' + (l.timestamp || '') + '</td></tr>'; }).join('') || '<tr><td colspan="4" style="color:#94A3B8">' + t('noAuditLogs') + '</td></tr>') + '</tbody></table></div>';
}
async function renderHallucination() {
  var det = await get('/api/v1/hallucination/detections?limit=20');
  var items = (det && det.detections) ? det.detections : [];
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('hallucinationDetections') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + t('hallucinationDesc') + '</p>' +
      '<table><thead><tr><th>ID</th><th>Score</th><th>Prompt</th><th>Corrected</th></tr></thead>' +
      '<tbody>' + (items.length ? items.map(function(d) { return '<tr><td style="font-family:monospace;font-size:12px">' + d.id + '</td><td>' + (d.score || 0).toFixed(2) + '</td><td style="font-size:13px;max-width:300px;word-break:break-all">' + (d.prompt_snippet || '').slice(0, 80) + '...</td><td>' + (d.corrected ? '<span class="badge badge-safe">' + t('yes') + '</span>' : '<span class="badge badge-toxic">' + t('no') + '</span>') + '</td></tr>'; }).join('') : '<tr><td colspan="4" style="color:#94A3B8">' + t('noHallucinations') + '</td></tr>') + '</tbody></table></div>';
}

async function renderSettings() {
  var settings = await get('/api/v1/settings');
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('settings') + '</h2>' +
      '<div class="form-group"><label>' + t('email') + '</label><input id="settings-email" style="width:100%;padding:12px;border-radius:12px;border:1px solid rgba(79,142,247,0.12);background:#0B1120;color:#E2E8F0;font-size:14px" value="' + ((settings && settings.admin_email) || '') + '"/></div>' +
      '<div class="form-group"><label>' + (lang === 'fr' ? 'Mot de Passe Actuel' : 'Current Password') + '</label><input type="password" id="settings-curr-pw" style="width:100%;padding:12px;border-radius:12px;border:1px solid rgba(79,142,247,0.12);background:#0B1120;color:#E2E8F0;font-size:14px" placeholder="' + t('settingsReq') + '"/></div>' +
      '<div class="form-group"><label>' + (lang === 'fr' ? 'Nouveau Mot de Passe' : 'New Password') + '</label><input type="password" id="settings-new-pw" style="width:100%;padding:12px;border-radius:12px;border:1px solid rgba(79,142,247,0.12);background:#0B1120;color:#E2E8F0;font-size:14px" placeholder="' + t('leaveBlank') + '"/></div>' +
      '<hr style="border-color:rgba(79,142,247,0.1);margin:24px 0"/>' +
      '<h3>' + (t['ar'] ? t('language') : 'Language / Langue') + '</h3>' +
      '<div style="display:flex;gap:8px;margin-top:12px">' +
        '<button class="filter-btn' + (lang === 'en' ? ' active' : '') + '" onclick="setLang(\'en\')" style="font-size:16px">English</button>' +
        '<button class="filter-btn' + (lang === 'fr' ? ' active' : '') + '" onclick="setLang(\'fr\')" style="font-size:16px">Français</button>' +
        '<button class="filter-btn' + (lang === 'ar' ? ' active' : '') + '" onclick="setLang(\'ar\')" style="font-size:16px">العربية</button>' +
      '</div>' +
      '<button class="btn-primary" onclick="saveAccountSettings()" style="width:auto;padding:10px 24px;margin-top:16px">' + t('saveSettings') + '</button></div>';
}
async function saveAccountSettings() {
  var body = { admin_email: document.getElementById('settings-email').value };
  var cp = document.getElementById('settings-curr-pw').value;
  var np = document.getElementById('settings-new-pw').value;
  if (cp && np) { body.current_password = cp; body.new_password = np; }
  await post('/api/v1/settings', body);
  showToast(t('settingsSaved'), 'success');
}

async function renderApiKeys() {
  var keys = await get('/api/v1/api-keys');
  var items = keys || [];
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('apiKeys') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + (lang === 'fr' ? 'Créez des clés API pour un accès programmatique.' : 'Create API keys for programmatic access to PolarisGate.') + '</p>' +
      '<button class="btn-primary" onclick="createApiKey()" style="width:auto;padding:8px 20px;margin-bottom:16px">' + t('createNewKey') + '</button><div id="new-key-display"></div>' +
      '<table><thead><tr><th>Key ID</th><th>Name</th><th>Created</th><th>Action</th></tr></thead>' +
      '<tbody>' + (items.map(function(k) { return '<tr><td style="font-family:monospace;font-size:12px">' + k.key_id + '</td><td>' + k.name + '</td><td style="font-size:12px;color:#94A3B8">' + (k.created_at || '') + '</td><td><button class="filter-btn" onclick="revokeApiKey(\'' + k.key_id + '\')">' + (lang === 'fr' ? 'Révoquer' : 'Revoke') + '</button></td></tr>'; }).join('') || '<tr><td colspan="4" style="color:#94A3B8">' + t('noApiKeys') + '</td></tr>') + '</tbody></table></div>';
}
async function createApiKey() {
  var name = prompt(lang === 'fr' ? 'Nom de la clé:' : 'Key name:', 'My API Key');
  if (!name) return;
  var result = await post('/api/v1/api-keys', { name: name });
  if (result) { document.getElementById('new-key-display').innerHTML = '<div class="card" style="margin-bottom:16px;border:1px solid #22c55e"><h3 style="color:#22c55e">' + t('keyCreated') + '</h3><p style="font-size:12px;color:#f59e0b;margin:8px 0">' + t('keyWarning') + '</p><div style="background:#0B1120;padding:12px;border-radius:8px;font-family:monospace;font-size:13px;word-break:break-all">' + result.api_key + '</div></div>'; renderApiKeys(); }
}
async function revokeApiKey(keyId) { if (!confirm((lang === 'fr' ? 'Révoquer la clé ' : 'Revoke key ') + keyId + '?')) return; await del('/api/v1/api-keys/' + keyId); renderApiKeys(); showToast(t('keyRevoked'), 'success'); }
async function renderWebhooks() {
  var wh = await get('/api/v1/settings/webhooks');
  var w = wh || { url: '', enabled: false, events: 'toxicity,pii' };
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('webhookSettings') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + t('webhookDesc') + '</p>' +
      '<div class="form-group"><label>' + t('webhookUrl') + '</label><input id="wh-url" style="width:100%;padding:12px;border-radius:12px;border:1px solid rgba(79,142,247,0.12);background:#0B1120;color:#E2E8F0;font-size:14px" value="' + (w.url || '') + '" placeholder="https://hooks.slack.com/services/..."/></div>' +
      '<div class="form-group"><label>' + t('events') + '</label><input id="wh-events" style="width:100%;padding:12px;border-radius:12px;border:1px solid rgba(79,142,247,0.12);background:#0B1120;color:#E2E8F0;font-size:14px" value="' + (w.events || 'toxicity,pii') + '" placeholder="toxicity,pii"/></div>' +
      '<div class="form-group"><label style="margin-bottom:8px;display:block">' + t('status') + '</label><label class="toggle"><input type="checkbox" id="wh-enabled" ' + (w.enabled ? 'checked' : '') + '><span class="toggle-slider"></span></label> <span style="color:#94A3B8;font-size:14px;vertical-align:top;line-height:26px">' + (w.enabled ? t('active') : t('inactive')) + '</span></div>' +
      '<button class="btn-primary" onclick="saveWebhook()" style="width:auto;padding:10px 24px">' + t('saveWebhook') + '</button></div>';
}
async function saveWebhook() { await post('/api/v1/settings/webhooks', { url: document.getElementById('wh-url').value, enabled: document.getElementById('wh-enabled').checked, events: document.getElementById('wh-events').value }); showToast(t('webhookSaved'), 'success'); }
async function renderUsers() {
  var users = await get('/api/v1/users');
  var items = users || [];
  document.getElementById('main-content').innerHTML =
    '<div class="card"><h2>' + t('userManagement') + '</h2><p style="color:#94A3B8;margin-bottom:12px">' + t('userDesc') + '</p>' +
      '<div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">' +
        '<input id="new-user-email" style="flex:1;min-width:200px;padding:10px 16px;border-radius:12px;border:1px solid rgba(79,142,247,0.12);background:#0B1120;color:#E2E8F0;font-size:14px" placeholder="' + t('userEmailPlaceholder') + '" onkeydown="if(event.key===\'Enter\')addUser()"/>' +
        '<input id="new-user-pw" type="password" style="flex:1;min-width:150px;padding:10px 16px;border-radius:12px;border:1px solid rgba(79,142,247,0.12);background:#0B1120;color:#E2E8F0;font-size:14px" placeholder="' + t('passwordPlaceholder') + '"/>' +
        '<select id="new-user-role" style="padding:10px 16px;border-radius:12px;border:1px solid rgba(79,142,247,0.12);background:#0B1120;color:#E2E8F0;font-size:14px"><option value="safety_officer">' + t('safetyOfficer') + '</option><option value="admin">' + t('admin') + '</option><option value="viewer">' + t('viewer') + '</option></select>' +
        '<button class="btn-primary" onclick="addUser()" style="width:auto;padding:10px 20px;margin-top:0">' + t('createUser') + '</button>' +
      '</div>' +
      '<table><thead><tr><th>' + t('email') + '</th><th>' + t('role') + '</th><th>' + t('status') + '</th><th>Action</th></tr></thead>' +
      '<tbody>' + (items.length ? items.map(function(u) { return '<tr><td>' + u.email + '</td><td>' + u.role + '</td><td>' + (u.active ? '<span class="badge badge-safe">' + t('active') + '</span>' : '<span class="badge badge-toxic">' + t('inactive') + '</span>') + '</td><td>' + (u.active ? '<button class="filter-btn" onclick="deactivateUser(\'' + u.email + '\')">' + t('deactivate') + '</button>' : '<span style="color:#94A3B8;font-size:12px">' + t('inactive') + '</span>') + '</td></tr>'; }).join('') : '<tr><td colspan="4" style="color:#94A3B8">' + (lang === 'fr' ? 'Aucun utilisateur créé' : 'No users created') + '</td></tr>') + '</tbody></table></div>';
}
async function addUser() {
  var email = document.getElementById('new-user-email').value.trim();
  var pw = document.getElementById('new-user-pw').value;
  var role = document.getElementById('new-user-role').value;
  if (!email || !pw) { showToast(t('emailPwRequired'), 'error'); return; }
  var result = await post('/api/v1/users', { email: email, password: pw, role: role });
  if (result) { renderUsers(); showToast(t('userCreated'), 'success'); }
}
async function deactivateUser(email) { if (!confirm((lang === 'fr' ? 'Désactiver ' : 'Deactivate ') + email + '?')) return; await del('/api/v1/users/' + encodeURIComponent(email)); renderUsers(); showToast(t('userDeactivated'), 'success'); }

(function init() {
  token = localStorage.getItem('polarisgate-token');
  if (token) { document.getElementById('login-screen').classList.add('hidden'); document.getElementById('dashboard-screen').classList.remove('hidden'); render(); }
})();