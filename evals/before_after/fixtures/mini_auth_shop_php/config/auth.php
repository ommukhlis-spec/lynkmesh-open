<?php

// Structural auth configuration for the fixture. No secrets or credentials.
return [
    'guard' => 'web',
    'session_key' => 'auth_user_id',
    'login_route' => '/login',
    'protected_prefixes' => ['/account'],
    'middleware' => 'auth',
];
