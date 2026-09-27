<?php
/*
 * nas4webtrees – Einrichtung im Browser.
 *
 * Apache zeigt diese Seite statt webtrees, solange webtrees nicht eingerichtet ist und niemand die
 * Einrichtung per Umgebung oder setup.json vorgegeben hat (siehe webtrees.conf). Sie fragt nur, was
 * ein Laie wissen kann – Stammbaum, Konto, privat ja/nein –, und legt die Angaben für den Nebenprozess
 * des Containers ab. Der füllt damit den Einrichtungsassistenten von webtrees aus (SQLite, keine
 * Datenbankfrage) und löscht die Datei. Danach greift die Umleitung nicht mehr, und der Browser
 * landet bei der Anmeldung von webtrees.
 *
 * Kommt der Aufruf nicht aus dem Heimnetz, verlangt die Seite den Einrichtungscode aus dem
 * Container-Protokoll – sonst könnte, wer die Adresse zuerst findet, den Administrator anlegen.
 */

declare(strict_types=1);

const RUN_DIR  = '/run/nas4webtrees';
const REQUEST  = RUN_DIR . '/setup-request.json';
const ERROR    = RUN_DIR . '/setup-error';
const CODE     = RUN_DIR . '/setup-code';
const DEFAULTS = RUN_DIR . '/setup-defaults.json';

header('Cache-Control: no-store');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');

$defaults = is_readable(DEFAULTS) ? (json_decode((string) file_get_contents(DEFAULTS), true) ?: []) : [];

// Sprache: Auswahl auf der Seite, sonst WT_LANG des Containers, sonst der Browser.
$lang = $_GET['lang'] ?? $_POST['lang'] ?? '';
if (!in_array($lang, ['de', 'en-US'], true)) {
    $lang = ($defaults['lang'] ?? '') !== '' ? (str_starts_with((string) $defaults['lang'], 'de') ? 'de' : 'en-US')
        : (str_starts_with(strtolower($_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? ''), 'de') ? 'de' : 'en-US');
}
$de = $lang === 'de';
$t  = static fn (string $german, string $english): string => $de ? $german : $english;
$h  = static fn (string $s): string => htmlspecialchars($s, ENT_QUOTES, 'UTF-8');

// Heimnetz: private, Loopback- und Link-Local-Adressen (wie api4webtrees).
$remote = (string) ($_SERVER['REMOTE_ADDR'] ?? '');
$home   = filter_var($remote, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) === false;

$values = [
    'tree_title' => $defaults['tree_title'] ?? $t('Mein Stammbaum', 'My family tree'),
    'user'       => '',
    'name'       => '',
    'email'      => '',
    'private'    => true,
];
$errors = [];
$state  = is_file(REQUEST) ? 'running' : 'form';

if (is_file(ERROR)) {
    $errors[] = $t('Die Einrichtung hat nicht geklappt: ', 'Setup failed: ') . trim((string) file_get_contents(ERROR));
}

if ($state === 'form' && ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    foreach (['tree_title', 'user', 'name', 'email'] as $key) {
        $values[$key] = trim((string) ($_POST[$key] ?? ''));
    }
    $values['private'] = isset($_POST['private']);
    $password = (string) ($_POST['password'] ?? '');

    if ($values['tree_title'] === '') {
        $errors[] = $t('Bitte gib deinem Stammbaum einen Namen.', 'Please give your family tree a name.');
    }
    if ($values['user'] === '' || preg_match('/[\s<>&"\']/', $values['user'])) {
        $errors[] = $t('Bitte einen Benutzernamen ohne Leerzeichen angeben.', 'Please enter a user name without spaces.');
    }
    if (filter_var($values['email'], FILTER_VALIDATE_EMAIL) === false) {
        $errors[] = $t('Bitte eine gültige E-Mail-Adresse angeben.', 'Please enter a valid email address.');
    }
    if (mb_strlen($password) < 8) {
        $errors[] = $t('Das Passwort braucht mindestens 8 Zeichen.', 'The password needs at least 8 characters.');
    } elseif ($password !== (string) ($_POST['password2'] ?? '')) {
        $errors[] = $t('Die beiden Passwörter stimmen nicht überein.', 'The two passwords do not match.');
    }
    if (!$home && !hash_equals(trim((string) @file_get_contents(CODE)), trim((string) ($_POST['code'] ?? '')))) {
        $errors[] = $t('Der Einrichtungscode stimmt nicht.', 'The setup code is not correct.');
    }

    if ($errors === []) {
        $request = [
            'user'       => $values['user'],
            'name'       => $values['name'] !== '' ? $values['name'] : $values['user'],
            'email'      => $values['email'],
            'password'   => $password,
            'tree_title' => $values['tree_title'],
            'private'    => $values['private'],
            'lang'       => $lang,
        ];
        @unlink(ERROR);
        $tmp = REQUEST . '.tmp';
        $old = umask(077);
        $ok  = file_put_contents($tmp, json_encode($request, JSON_UNESCAPED_UNICODE)) !== false && rename($tmp, REQUEST);
        umask($old);
        if ($ok) {
            header('Location: ./?lang=' . rawurlencode($lang), true, 303);
            exit;
        }
        $errors[] = $t('Die Angaben ließen sich nicht speichern – bitte das Container-Protokoll ansehen.',
            'Could not save the details – please check the container log.');
    }
}

?><!doctype html>
<html lang="<?= $de ? 'de' : 'en' ?>">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<?php if ($state === 'running') : ?><meta http-equiv="refresh" content="3;url=/"><?php endif ?>
<title><?= $h($t('webtrees einrichten', 'Set up webtrees')) ?></title>
<style>
  :root { --ink:#1d2733; --muted:#5b6673; --line:#d5dbe1; --bg:#f3f5f7; --card:#fff; --blue:#1f5f99; --green:#3e8e41; --red:#b3261e; }
  * { box-sizing: border-box; }
  body { margin:0; font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; color:var(--ink); background:var(--bg); }
  main { max-width:34rem; margin:2rem auto; padding:0 1rem; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:1.5rem; }
  header { display:flex; align-items:center; gap:.75rem; margin-bottom:1rem; }
  header svg { width:48px; height:48px; flex:none; }
  h1 { font-size:1.4rem; margin:0; }
  .sub { color:var(--muted); margin:.25rem 0 1.25rem; }
  label { display:block; font-weight:600; margin:1rem 0 .3rem; }
  .hint { color:var(--muted); font-size:.9rem; font-weight:400; }
  input[type=text], input[type=email], input[type=password] { width:100%; padding:.6rem .7rem; font:inherit; border:1px solid var(--line); border-radius:8px; }
  input:focus { outline:2px solid var(--blue); outline-offset:1px; }
  .check { display:flex; gap:.6rem; align-items:flex-start; margin-top:1.2rem; font-weight:400; }
  .check input { margin-top:.3rem; }
  button { margin-top:1.5rem; width:100%; padding:.75rem; font:inherit; font-weight:600; color:#fff; background:var(--blue); border:0; border-radius:8px; cursor:pointer; }
  .errors { background:#fdecea; color:var(--red); border-radius:8px; padding:.75rem 1rem; margin-bottom:1rem; }
  .errors p { margin:.2rem 0; }
  .lang { text-align:right; font-size:.9rem; margin-bottom:.5rem; }
  .lang a { color:var(--blue); }
  .spinner { width:2.5rem; height:2.5rem; margin:1rem auto; border:4px solid var(--line); border-top-color:var(--green); border-radius:50%; animation:spin 1s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  footer { color:var(--muted); font-size:.85rem; text-align:center; margin-top:1rem; }
</style>
</head>
<body>
<main>
<div class="lang"><a href="?lang=<?= $de ? 'en-US' : 'de' ?>"><?= $de ? 'English' : 'Deutsch' ?></a></div>
<div class="card">
<header>
  <svg viewBox="0 0 256 256" aria-hidden="true"><g stroke="#1F5F99" stroke-width="12" stroke-linecap="round" fill="none"><path d="M128 200 V150 M128 150 H68 V112 M128 150 H188 V112 M68 112 H40 V76 M68 112 H96 V76 M188 112 H160 V76 M188 112 H216 V76"/></g><circle cx="128" cy="210" r="24" fill="#1F5F99"/><g fill="#3E8E41"><circle cx="40" cy="58" r="20"/><circle cx="96" cy="58" r="20"/><circle cx="160" cy="58" r="20"/><circle cx="216" cy="58" r="20"/></g></svg>
  <h1><?= $h($t('Willkommen bei webtrees', 'Welcome to webtrees')) ?></h1>
</header>

<?php if ($state === 'running') : ?>
  <p class="sub"><?= $h($t('Dein Stammbaum wird eingerichtet. Das dauert nur einen Moment – danach erscheint die Anmeldung von webtrees.',
      'Your family tree is being set up. This takes a moment – then the webtrees sign-in appears.')) ?></p>
  <div class="spinner" role="status" aria-label="<?= $h($t('Bitte warten', 'Please wait')) ?>"></div>
<?php else : ?>
  <p class="sub"><?= $h($t('Noch zwei Minuten, dann ist dein Stammbaum bereit. Die Angaben gelten nur für webtrees.',
      'Two more minutes and your family tree is ready. These details are for webtrees only.')) ?></p>

  <?php if ($errors !== []) : ?>
    <div class="errors" role="alert"><?php foreach ($errors as $e) : ?><p><?= $h($e) ?></p><?php endforeach ?></div>
  <?php endif ?>

  <form method="post" action="./">
    <input type="hidden" name="lang" value="<?= $h($lang) ?>">

    <label for="tree_title"><?= $h($t('Name des Stammbaums', 'Name of the family tree')) ?></label>
    <input type="text" id="tree_title" name="tree_title" required value="<?= $h((string) $values['tree_title']) ?>">

    <label for="user"><?= $h($t('Dein Benutzername', 'Your user name')) ?> <span class="hint"><?= $h($t('– damit meldest du dich an', '– you sign in with it')) ?></span></label>
    <input type="text" id="user" name="user" required autocomplete="username" value="<?= $h((string) $values['user']) ?>">

    <label for="name"><?= $h($t('Dein Name', 'Your name')) ?> <span class="hint"><?= $h($t('(freiwillig)', '(optional)')) ?></span></label>
    <input type="text" id="name" name="name" autocomplete="name" value="<?= $h((string) $values['name']) ?>">

    <label for="email"><?= $h($t('E-Mail-Adresse', 'Email address')) ?></label>
    <input type="email" id="email" name="email" required autocomplete="email" value="<?= $h((string) $values['email']) ?>">

    <label for="password"><?= $h($t('Passwort', 'Password')) ?> <span class="hint"><?= $h($t('– mindestens 8 Zeichen', '– at least 8 characters')) ?></span></label>
    <input type="password" id="password" name="password" required minlength="8" autocomplete="new-password">

    <label for="password2"><?= $h($t('Passwort wiederholen', 'Repeat password')) ?></label>
    <input type="password" id="password2" name="password2" required minlength="8" autocomplete="new-password">

    <?php if (!$home) : ?>
      <label for="code"><?= $h($t('Einrichtungscode', 'Setup code')) ?>
        <span class="hint"><?= $h($t('– steht im Protokoll des Containers, weil du nicht aus dem Heimnetz zugreifst', '– shown in the container log, because you are not accessing from your home network')) ?></span></label>
      <input type="text" id="code" name="code" required autocomplete="off" inputmode="numeric">
    <?php endif ?>

    <label class="check"><input type="checkbox" name="private" <?= $values['private'] ? 'checked' : '' ?>>
      <span><?= $h($t('Stammbaum nur für angemeldete Benutzer', 'Family tree for signed-in users only')) ?><br>
      <span class="hint"><?= $h($t('Empfohlen: Besucher sehen nichts, Konten für deine Verwandten legst du in webtrees an.',
          'Recommended: visitors see nothing; you create accounts for your relatives in webtrees.')) ?></span></span></label>

    <button type="submit"><?= $h($t('Stammbaum einrichten', 'Set up family tree')) ?></button>
  </form>
<?php endif ?>
</div>
<footer>nas4webtrees · <?= $h($t('das originale webtrees mit api4webtrees', 'the original webtrees with api4webtrees')) ?></footer>
</main>
</body>
</html>
