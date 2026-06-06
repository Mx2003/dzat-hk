<?php
require_once '/var/www/html/bootstrap.php';
$pdo = (new Espo\Core\Application())->getContainer()->get('entityManager')->getPDO();

echo "=== Final Verification ===\n\n";

echo "[User Types]\n";
$stmt = $pdo->query("SELECT user_name, type FROM user WHERE type NOT IN ('api', 'system') ORDER BY type, user_name");
while ($r = $stmt->fetch()) {
    echo sprintf("  %-15s type=%s\n", $r['user_name'], $r['type']);
}

echo "\n[Team Assignments]\n";
$stmt = $pdo->query("SELECT u.user_name, t.name as tname FROM user u JOIN team_user tu ON u.id=tu.user_id JOIN team t ON t.id=tu.team_id ORDER BY t.name, u.user_name");
while ($r = $stmt->fetch()) {
    echo sprintf("  %-15s -> %s\n", $r['user_name'], $r['tname']);
}

echo "\n[Role Assignments]\n";
$stmt = $pdo->query("SELECT u.user_name, r.name as rname FROM user u JOIN role_user ru ON u.id=ru.user_id JOIN role r ON r.id=ru.role_id WHERE u.type='regular' ORDER BY r.name, u.user_name");
while ($r = $stmt->fetch()) {
    echo sprintf("  %-15s -> %s\n", $r['user_name'], $r['rname']);
}

echo "\n[Lead Distribution]\n";
$stmt = $pdo->query("SELECT u.user_name, COUNT(*) as cnt FROM `lead` l JOIN user u ON u.id=l.assigned_user_id WHERE l.deleted=0 GROUP BY u.id, u.user_name ORDER BY cnt DESC");
while ($r = $stmt->fetch()) {
    echo sprintf("  %-15s: %d leads\n", $r['user_name'], $r['cnt']);
}

echo "\n[Unassigned]\n";
$remain = $pdo->query("SELECT COUNT(*) FROM `lead` WHERE deleted=0 AND assigned_user_id IS NULL")->fetchColumn();
echo "  Unassigned: $remain\n";

$total = $pdo->query("SELECT COUNT(*) FROM `lead` WHERE deleted=0")->fetchColumn();
echo "  Total active: $total\n";

echo "\n=== Done ===\n";
