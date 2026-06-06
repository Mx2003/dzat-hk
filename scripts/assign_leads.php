<?php
/**
 * Round-robin lead assignment - only active (deleted=0) leads
 */
require_once "/var/www/html/bootstrap.php";
use Espo\Core\Application;

$app = new Application();
$pdo = $app->getContainer()->get("entityManager")->getPDO();

echo "=== Lead Round-Robin Assignment ===\n\n";

$waimaoTeamId = 'f2abdbc4da34cf06e';
$neimaoTeamId = 'e97c6626987f655ba';

// Step 0: Reset all existing assignments
echo "Step 0: Resetting existing assignments...\n";
$reset = $pdo->exec("UPDATE `lead` SET assigned_user_id = NULL, teams_ids = NULL WHERE assigned_user_id IS NOT NULL AND assigned_user_id != ''");
echo "  Reset $reset leads\n\n";

// Count active leads
$total = $pdo->query("SELECT COUNT(*) FROM `lead` WHERE deleted = 0")->fetchColumn();
echo "Active leads (deleted=0): $total\n\n";

// Get team members
$getMembers = function($teamId) use ($pdo) {
    $stmt = $pdo->prepare(
        "SELECT u.id, u.user_name FROM `user` u
         JOIN team_user tu ON u.id = tu.user_id
         WHERE tu.team_id = :tid AND u.type = 'regular'"
    );
    $stmt->execute(['tid' => $teamId]);
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
};

$waimaoMembers = $getMembers($waimaoTeamId);
$neimaoMembers = $getMembers($neimaoTeamId);

echo "外贸组成员: " . implode(', ', array_column($waimaoMembers, 'user_name')) . "\n";
echo "内贸组成员: " . implode(', ', array_column($neimaoMembers, 'user_name')) . "\n\n";

if ($total == 0) { echo "Nothing to assign!\n"; exit(0); }

$assignTeam = function($members, $teamId, $label) use ($pdo) {
    if (!$members) { echo "$label: no members, skip\n"; return; }
    $memberIds = array_column($members, 'id');

    // Build country filter + deleted=0
    $deletedFilter = "deleted = 0 AND (assigned_user_id IS NULL OR assigned_user_id = '')";
    if ($teamId === 'e97c6626987f655ba') {
        $where = "$deletedFilter AND LOWER(COALESCE(address_country, '')) IN ('中国', 'china', 'cn', 'chinese')";
    } else {
        $where = "$deletedFilter AND (address_country IS NULL OR address_country = '' OR LOWER(address_country) NOT IN ('中国', 'china', 'cn', 'chinese'))";
    }

    $count = $pdo->query("SELECT COUNT(*) FROM `lead` WHERE $where")->fetchColumn();
    echo "$label: $count leads to assign\n";
    if ($count == 0) return;

    $batchSize = 200;
    $totalAssigned = 0;

    while ($totalAssigned < $count) {
        $stmt = $pdo->query("SELECT id FROM `lead` WHERE $where LIMIT $batchSize OFFSET 0");
        $batch = $stmt->fetchAll(PDO::FETCH_ASSOC);
        if (!$batch) break;

        foreach ($batch as $lead) {
            $uid = $memberIds[$totalAssigned % count($memberIds)];
            $pdo->exec("UPDATE `lead` SET assigned_user_id = '$uid' WHERE id = '{$lead['id']}'");
            $totalAssigned++;
        }
        echo "  $totalAssigned / $count\n";
    }
    echo "$label: Done ($totalAssigned assigned)\n";
};

$assignTeam($waimaoMembers, $waimaoTeamId, '外贸组');
echo "\n";
$assignTeam($neimaoMembers, $neimaoTeamId, '内贸组');

// Summary
echo "\n=== Summary ===\n";
foreach (array_merge($waimaoMembers, $neimaoMembers) as $m) {
    $cnt = $pdo->query("SELECT COUNT(*) FROM `lead` WHERE assigned_user_id = '{$m['id']}' AND deleted = 0")->fetchColumn();
    echo "  {$m['user_name']}: $cnt leads\n";
}

$remaining = $pdo->query("SELECT COUNT(*) FROM `lead` WHERE deleted = 0 AND (assigned_user_id IS NULL OR assigned_user_id = '')")->fetchColumn();
echo "\nUnassigned remaining: $remaining\n";
echo "Done!\n";
