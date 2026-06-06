<?php
require_once "/var/www/html/bootstrap.php";
$pdo = (new Espo\Core\Application())->getContainer()->get("entityManager")->getPDO();

// Reset only active records
$r = $pdo->exec("UPDATE `lead` SET assigned_user_id = NULL, teams_ids = NULL WHERE deleted = 0");
echo "Reset $r active records\n";

// Team members
$stmt = $pdo->query("SELECT u.id, u.user_name FROM `user` u JOIN team_user tu ON u.id=tu.user_id WHERE tu.team_id='f2abdbc4da34cf06e' AND u.type='regular'");
$members = $stmt->fetchAll(PDO::FETCH_ASSOC);
$mIds = array_column($members, 'id');
echo "Members: " . implode(', ', array_column($members, 'user_name')) . "\n";

// Get all active unassigned foreign records
$rows = $pdo->query("SELECT id FROM `lead` WHERE deleted = 0 AND (assigned_user_id IS NULL OR assigned_user_id = '') AND (address_country IS NULL OR address_country = '' OR LOWER(address_country) NOT IN ('中国', 'china', 'cn', 'chinese'))")->fetchAll(PDO::FETCH_ASSOC);
$total = count($rows);
echo "To assign: $total\n\n";

$idx = 0;
foreach ($rows as $row) {
    $uid = $mIds[$idx % count($mIds)];
    $pdo->exec("UPDATE `lead` SET assigned_user_id = '$uid' WHERE id = '{$row['id']}'");
    $idx++;
    if ($idx % 100 == 0) echo "  $idx / $total\n";
}

echo "\nDone: $idx assigned\n\n=== Summary ===\n";
foreach ($members as $m) {
    $cnt = $pdo->query("SELECT COUNT(*) FROM `lead` WHERE assigned_user_id = '{$m['id']}' AND deleted = 0")->fetchColumn();
    echo "  {$m['user_name']}: $cnt records\n";
}

$remaining = $pdo->query("SELECT COUNT(*) FROM `lead` WHERE deleted = 0 AND (assigned_user_id IS NULL OR assigned_user_id = '')")->fetchColumn();
echo "\nUnassigned remaining: $remaining\n";
