<?php
/**
 * EspoCRM RBAC Setup Script
 * Run: docker exec dzat-espocrm php /var/www/html/scripts/setup_crm_rbac.php
 *
 * Uses direct SQL to avoid hook dependencies on CLI 'user' service.
 */

require_once "bootstrap.php";

use Espo\Core\Application;

$app = new Application();
$pdo = $app->getContainer()->get("entityManager")->getPDO();

echo "=== EspoCRM RBAC Setup ===\n\n";

// Helper: generate a UUID-like ID
function genId() {
    return substr(bin2hex(random_bytes(9)), 0, 17);
}

// ============================================
// STEP 1: Fix User Types
// ============================================
echo "STEP 1: Adjusting User Types...\n";

$userTypeChanges = [
    'maxiaowei' => 'admin',
    'wangjiahui' => 'regular',
    'chenruipeng' => 'regular',
    'guolisiqin' => 'regular',
    'mayi' => 'regular',
    'penghaohang' => 'regular',
];

foreach ($userTypeChanges as $username => $newType) {
    $pdo->prepare("UPDATE user SET type = :type WHERE user_name = :uname")
        ->execute(['type' => $newType, 'uname' => $username]);
    echo "  $username -> $newType ✓\n";
}

echo "\n";

// ============================================
// STEP 2: Create Teams (via SQL)
// ============================================
echo "STEP 2: Creating Teams...\n";

$teamIds = [];
$teamsToCreate = [
    '外贸组' => '处理海外客户 (非中国)',
    '内贸组' => '处理中国客户',
];

foreach ($teamsToCreate as $name => $desc) {
    $stmt = $pdo->prepare("SELECT id FROM team WHERE name = :name");
    $stmt->execute(['name' => $name]);
    $existing = $stmt->fetchColumn();

    if ($existing) {
        $teamIds[$name] = $existing;
        echo "  $name: already exists (id=$existing) ✓\n";
    } else {
        $id = genId();
        $pdo->prepare("INSERT INTO team (id, name) VALUES (:id, :name)")
            ->execute(['id' => $id, 'name' => $name]);
        $teamIds[$name] = $id;
        echo "  $name: created (id=$id) ✓\n";
    }
}

$waimaoTeamId = $teamIds['外贸组'];
$neimaoTeamId = $teamIds['内贸组'];

echo "\n";

// ============================================
// STEP 3: Create Roles (via SQL)
// ============================================
echo "STEP 3: Creating Roles...\n";

// Role data for 业务员 (Salesperson) - own records only
$salesData = json_encode([
    'Lead' => ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'no', 'stream' => 'own'],
    'Contact' => ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'no', 'stream' => 'own'],
    'Account' => ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'no', 'stream' => 'own'],
    'TargetList' => ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'no'],
    'OutreachRecord' => ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'no'],
    'Email' => ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'no'],
    'Calendar' => ['create' => 'yes', 'read' => 'yes'],
    'Meeting' => ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'no'],
    'Call' => ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'no'],
    'Task' => ['create' => 'yes', 'read' => 'own', 'edit' => 'own', 'delete' => 'no'],
    'Document' => ['create' => 'yes', 'read' => 'own'],
    'Team' => ['create' => 'no', 'read' => 'yes', 'edit' => 'no', 'delete' => 'no'],
    'User' => ['create' => 'no', 'read' => 'yes', 'edit' => 'no', 'delete' => 'no'],
]);

// Role data for 经理 (Manager) - team records
$managerData = json_encode([
    'Lead' => ['create' => 'yes', 'read' => 'team', 'edit' => 'team', 'delete' => 'no', 'stream' => 'team'],
    'Contact' => ['create' => 'yes', 'read' => 'team', 'edit' => 'team', 'delete' => 'no', 'stream' => 'team'],
    'Account' => ['create' => 'yes', 'read' => 'team', 'edit' => 'team', 'delete' => 'no', 'stream' => 'team'],
    'TargetList' => ['create' => 'yes', 'read' => 'team', 'edit' => 'team', 'delete' => 'no'],
    'OutreachRecord' => ['create' => 'yes', 'read' => 'team', 'edit' => 'team', 'delete' => 'no'],
    'Email' => ['create' => 'yes', 'read' => 'team', 'edit' => 'team', 'delete' => 'no'],
    'Calendar' => ['create' => 'yes', 'read' => 'yes'],
    'Meeting' => ['create' => 'yes', 'read' => 'team', 'edit' => 'team', 'delete' => 'no'],
    'Call' => ['create' => 'yes', 'read' => 'team', 'edit' => 'team', 'delete' => 'no'],
    'Task' => ['create' => 'yes', 'read' => 'team', 'edit' => 'team', 'delete' => 'no'],
    'Document' => ['create' => 'yes', 'read' => 'team'],
    'Team' => ['create' => 'no', 'read' => 'yes', 'edit' => 'no', 'delete' => 'no'],
    'User' => ['create' => 'no', 'read' => 'team', 'edit' => 'no', 'delete' => 'no'],
]);

$roleIds = [];
$rolesToCreate = [
    '业务员' => ['data' => $salesData, 'assignmentPermission' => 'no', 'exportPermission' => 'yes', 'massUpdatePermission' => 'no', 'userPermission' => 'no'],
    '经理' => ['data' => $managerData, 'assignmentPermission' => 'team', 'exportPermission' => 'yes', 'massUpdatePermission' => 'yes', 'userPermission' => 'team'],
];

foreach ($rolesToCreate as $name => $fields) {
    $stmt = $pdo->prepare("SELECT id FROM role WHERE name = :name");
    $stmt->execute(['name' => $name]);
    $existing = $stmt->fetchColumn();

    if ($existing) {
        $roleIds[$name] = $existing;
        echo "  $name: already exists (id=$existing) ✓\n";
    } else {
        $id = genId();
        $pdo->prepare("INSERT INTO role (id, name, data, assignment_permission, export_permission, mass_update_permission, user_permission)
            VALUES (:id, :name, :data, :ap, :ep, :mup, :up)")
            ->execute([
                'id' => $id,
                'name' => $name,
                'data' => $fields['data'],
                'ap' => $fields['assignmentPermission'],
                'ep' => $fields['exportPermission'],
                'mup' => $fields['massUpdatePermission'],
                'up' => $fields['userPermission'],
            ]);
        $roleIds[$name] = $id;
        echo "  $name: created (id=$id) ✓\n";
    }
}

echo "\n";

// ============================================
// STEP 4: Assign Users to Teams and Roles
// ============================================
echo "STEP 4: Assigning Users to Teams and Roles...\n";

$userAssignments = [
    'wangjiahui' => ['经理', '外贸组', '外贸组'],
    'chenruipeng' => ['业务员', '外贸组', '外贸组'],
    'guolisiqin' => ['业务员', '外贸组', '外贸组'],
    'mayi' => ['业务员', '内贸组', '内贸组'],
    'penghaohang' => ['业务员', '内贸组', '内贸组'],
];

foreach ($userAssignments as $username => [$roleName, $teamName, $defaultTeam]) {
    $roleId = $roleIds[$roleName];
    $teamId = $teamIds[$teamName];
    $defaultTeamId = $teamIds[$defaultTeam];

    // Get user ID
    $stmt = $pdo->prepare("SELECT id FROM user WHERE user_name = :uname");
    $stmt->execute(['uname' => $username]);
    $userId = $stmt->fetchColumn();

    if (!$userId) {
        echo "  $username: NOT FOUND ✗\n";
        continue;
    }

    // Insert into role_user (skip if exists)
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM role_user WHERE user_id = :uid AND role_id = :rid");
    $stmt->execute(['uid' => $userId, 'rid' => $roleId]);
    if ($stmt->fetchColumn() == 0) {
        $pdo->prepare("INSERT INTO role_user (role_id, user_id) VALUES (:rid, :uid)")
            ->execute(['rid' => $roleId, 'uid' => $userId]);
    }

    // Insert into team_user (skip if exists)
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM team_user WHERE user_id = :uid AND team_id = :tid");
    $stmt->execute(['uid' => $userId, 'tid' => $teamId]);
    if ($stmt->fetchColumn() == 0) {
        $pdo->prepare("INSERT INTO team_user (team_id, user_id) VALUES (:tid, :uid)")
            ->execute(['tid' => $teamId, 'uid' => $userId]);
    }

    // Set default team
    $pdo->prepare("UPDATE user SET default_team_id = :dtid WHERE id = :uid")
        ->execute(['dtid' => $defaultTeamId, 'uid' => $userId]);

    echo "  $username: role=$roleName, team=$teamName ✓\n";
}

echo "\n=== Setup Complete ===\n";
echo "Team IDs: 外贸组=$waimaoTeamId, 内贸组=$neimaoTeamId\n";
echo "Role IDs: 业务员={$roleIds['业务员']}, 经理={$roleIds['经理']}\n";
