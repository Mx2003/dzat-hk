<?php
require_once '/var/www/html/bootstrap.php';
$pdo = (new Espo\Core\Application())->getContainer()->get('entityManager')->getPDO();

// Get members
$stmt = $pdo->query("SELECT u.id, u.user_name FROM user u JOIN team_user tu ON u.id=tu.user_id WHERE tu.team_id='f2abdbc4da34cf06e' AND u.type='regular'");
$members = $stmt->fetchAll(PDO::FETCH_ASSOC);
$mIds = array_column($members, 'id');
$mNames = array_column($members, 'user_name');
echo "Members: " . implode(', ', $mNames) . "\n";

// Get unassigned active leads
$rows = $pdo->query("SELECT id FROM `lead` WHERE deleted=0 AND assigned_user_id IS NULL")->fetchAll(PDO::FETCH_ASSOC);
$total = count($rows);
echo "Total to assign: $total\n";

// Round-robin
$idx = 0;
foreach ($rows as $row) {
    $uid = $mIds[$idx % count($mIds)];
    $lid = $row['id'];
    $pdo->exec("UPDATE `lead` SET assigned_user_id='$uid' WHERE id='$lid'");
    $idx++;
    if ($idx % 100 === 0) echo "  $idx / $total\n";
}

echo "Assigned: $idx\n\n=== Summary ===\n";
foreach ($members as $m) {
    $cnt = $pdo->query("SELECT COUNT(*) FROM `lead` WHERE assigned_user_id='{$m['id']}' AND deleted=0")->fetchColumn();
    echo "  {$m['user_name']}: $cnt leads\n";
}

$remain = $pdo->query("SELECT COUNT(*) FROM `lead` WHERE deleted=0 AND assigned_user_id IS NULL")->fetchColumn();
echo "\nUnassigned remaining: $remain\n";
echo "Done!\n";
