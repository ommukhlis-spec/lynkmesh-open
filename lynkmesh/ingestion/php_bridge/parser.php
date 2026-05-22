<?php
/**
 * LynkMesh Universal PHP AST Parser v14 - Semantic Aware Extractor
 * ============================================================
 * 
 * Output IR is now fully compatible with LynkMesh propagation engine:
 * - All call objects carry `assign_to` instead of `var`
 * - Assignment records carry `source_call` and `line` for exact merging
 * - Consistent schema across all call types (method, static, function)
 * - Every call now includes its source line number
 * - CRITICAL FIX: Method calls now ALWAYS carry `target` (class hint) when possible,
 *   resolving $this->property->method() using constructor property tracking.
 * - CRITICAL FIX: Class nodes now include `file` field to prevent identity collision
 *   and enable proper symbol resolution.
 */

error_reporting(E_ALL);
ini_set('display_errors', 0);
ini_set('log_errors', 1);
ini_set('error_log', __DIR__ . '/parser_errors.log');

header('Content-Type: application/json');

require __DIR__ . '/vendor/autoload.php';

use PhpParser\Error;
use PhpParser\Node;
use PhpParser\ParserFactory;
use PhpParser\NodeTraverser;
use PhpParser\NodeVisitorAbstract;
use PhpParser\NodeVisitor\NameResolver;
use PhpParser\NodeVisitor\ParentConnectingVisitor;

if ($argc < 2) {
    echo json_encode(["error" => true, "message" => "No path provided"]);
    exit(1);
}

$inputPath = $argv[1];
$files = [];

if (is_dir($inputPath)) {
    $iterator = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($inputPath, RecursiveDirectoryIterator::SKIP_DOTS)
    );
    foreach ($iterator as $file) {
        if (!$file->isFile()) continue;
        if (strtolower($file->getExtension()) !== "php") continue;
        $path = $file->getPathname();
        if (
            strpos($path, DIRECTORY_SEPARATOR . "vendor" . DIRECTORY_SEPARATOR) !== false ||
            strpos($path, DIRECTORY_SEPARATOR . ".git" . DIRECTORY_SEPARATOR) !== false ||
            strpos($path, DIRECTORY_SEPARATOR . "node_modules" . DIRECTORY_SEPARATOR) !== false
        ) {
            continue;
        }
        $files[] = $path;
    }
} else {
    if (!file_exists($inputPath)) {
        echo json_encode(["error" => true, "message" => "File not found"]);
        exit(1);
    }
    $files[] = $inputPath;
}

$parser = (new ParserFactory)->create(ParserFactory::PREFER_PHP7);

class GenericASTVisitor extends NodeVisitorAbstract {
    private $output;
    private $currentStructureIndex = null;
    private $currentMethodIndex = null;
    private $localVarTypes = [];
    private $routeDefinitions = [];

    // 🔥 NEW: store the file path being parsed
    private string $currentFilePath;

    private $facadeMap = [
        'App'       => 'Illuminate\\Support\\Facades\\App',
        'Artisan'   => 'Illuminate\\Support\\Facades\\Artisan',
        'Auth'      => 'Illuminate\\Support\\Facades\\Auth',
        'Blade'     => 'Illuminate\\Support\\Facades\\Blade',
        'Broadcast' => 'Illuminate\\Support\\Facades\\Broadcast',
        'Bus'       => 'Illuminate\\Support\\Facades\\Bus',
        'Cache'     => 'Illuminate\\Support\\Facades\\Cache',
        'Config'    => 'Illuminate\\Support\\Facades\\Config',
        'Cookie'    => 'Illuminate\\Support\\Facades\\Cookie',
        'Crypt'     => 'Illuminate\\Support\\Facades\\Crypt',
        'DB'        => 'Illuminate\\Support\\Facades\\DB',
        'Event'     => 'Illuminate\\Support\\Facades\\Event',
        'File'      => 'Illuminate\\Support\\Facades\\File',
        'Gate'      => 'Illuminate\\Support\\Facades\\Gate',
        'Hash'      => 'Illuminate\\Support\\Facades\\Hash',
        'Lang'      => 'Illuminate\\Support\\Facades\\Lang',
        'Log'       => 'Illuminate\\Support\\Facades\\Log',
        'Mail'      => 'Illuminate\\Support\\Facades\\Mail',
        'Notification' => 'Illuminate\\Support\\Facades\\Notification',
        'Password'  => 'Illuminate\\Support\\Facades\\Password',
        'Queue'     => 'Illuminate\\Support\\Facades\\Queue',
        'Redirect'  => 'Illuminate\\Support\\Facades\\Redirect',
        'Redis'     => 'Illuminate\\Support\\Facades\\Redis',
        'Request'   => 'Illuminate\\Support\\Facades\\Request',
        'Response'  => 'Illuminate\\Support\\Facades\\Response',
        'Route'     => 'Illuminate\\Support\\Facades\\Route',
        'Schema'    => 'Illuminate\\Support\\Facades\\Schema',
        'Session'   => 'Illuminate\\Support\\Facades\\Session',
        'Storage'   => 'Illuminate\\Support\\Facades\\Storage',
        'URL'       => 'Illuminate\\Support\\Facades\\URL',
        'Validator' => 'Illuminate\\Support\\Facades\\Validator',
        'View'      => 'Illuminate\\Support\\Facades\\View',
    ];

    public function __construct(array &$output, string $filePath) {
        $this->output =& $output;
        $this->currentFilePath = $filePath;  // 🔥 simpan jalur file
    }
    
    public function getRouteDefinitions() {
        return $this->routeDefinitions;
    }

    private function resolveName($nameNode) {
        if (!$nameNode instanceof Node\Name) return null;
        $resolved = $nameNode->getAttribute('resolvedName');
        return $resolved ? $resolved->toString() : $nameNode->toString();
    }

    private function resolveType($typeNode) {
        if ($typeNode === null) return null;
        if ($typeNode instanceof Node\Name) {
            return $this->resolveName($typeNode);
        }
        if ($typeNode instanceof Node\Identifier) {
            return $typeNode->toString();
        }
        if ($typeNode instanceof Node\NullableType) {
            $inner = $this->resolveType($typeNode->type);
            return $inner ? '?' . $inner : null;
        }
        if ($typeNode instanceof Node\UnionType) {
            $types = [];
            foreach ($typeNode->types as $t) {
                $resolved = $this->resolveType($t);
                if ($resolved) $types[] = $resolved;
            }
            return implode('|', $types);
        }
        return null;
    }

    private function buildStructureBase($node, $type) {
        $resolvedName = $node->namespacedName ?? null;
        return [
            "type"       => $type,
            "name"       => $node->name ? $node->name->toString() : null,
            "fqn"        => $resolvedName ? $resolvedName->toString() : ($node->name ? $node->name->toString() : null),
            "extends"    => [],
            "implements" => [],
            "traits"     => [],
            "properties" => [],
            "methods"    => [],
            "file"       => $this->currentFilePath,  // 🔥 tambahkan kunci file
        ];
    }

    private function setNodeType(Node $node, $type) {
        $node->setAttribute('resolvedType', $type);
    }

    private function getNodeType(Node $node) {
        return $node->getAttribute('resolvedType');
    }

    private function extractRouteDefinition($node) {
        if (!$node instanceof Node\Expr\StaticCall) return null;
        $classNode = $node->class;
        if (!$classNode instanceof Node\Name) return null;
        $className = $classNode->toString();
        if ($className !== 'Route') return null;
        if (!$node->name instanceof Node\Identifier) return null;
        $httpMethod = $node->name->toString();
        $allowedMethods = ['get', 'post', 'put', 'delete', 'patch', 'options', 'any'];
        if (!in_array(strtolower($httpMethod), $allowedMethods)) return null;
        
        $uri = null; $controller = null; $controllerMethod = null;
        if (isset($node->args[0])) {
            $arg0 = $node->args[0]->value;
            if ($arg0 instanceof Node\Scalar\String_) $uri = $arg0->value;
        }
        if (isset($node->args[1])) {
            $arg1 = $node->args[1]->value;
            if ($arg1 instanceof Node\Expr\Array_) {
                foreach ($arg1->items as $item) {
                    if ($item->value instanceof Node\Expr\ClassConstFetch && $item->value->name->toString() === 'class') {
                        $controller = $this->resolveName($item->value->class);
                    } elseif ($item->value instanceof Node\Scalar\String_) {
                        $controllerMethod = $item->value->value;
                    }
                }
            } elseif ($arg1 instanceof Node\Scalar\String_ && strpos($arg1->value, '@') !== false) {
                list($controller, $controllerMethod) = explode('@', $arg1->value, 2);
            }
        }
        if ($uri) {
            return [
                'http_method' => strtoupper($httpMethod),
                'uri' => $uri,
                'controller' => $controller,
                'controller_method' => $controllerMethod,
                'line' => $node->getLine()
            ];
        }
        return null;
    }
   
    private function extractCustomRouteDefinition($node) {
        if (!$node instanceof Node\Expr\MethodCall) return null;
        if (!$node->var instanceof Node\Expr\Variable) return null;
        if ($node->var->name !== 'router') return null;
        if (!$node->name instanceof Node\Identifier) return null;
        $httpMethod = $node->name->toString();
        $allowedMethods = ['get', 'post', 'put', 'delete', 'patch', 'options', 'any'];
        if (!in_array(strtolower($httpMethod), $allowedMethods)) return null;
        
        $uri = null; $controller = null; $controllerMethod = null;
        if (isset($node->args[0])) {
            $arg0 = $node->args[0]->value;
            if ($arg0 instanceof Node\Scalar\String_) $uri = $arg0->value;
        }
        if (isset($node->args[1])) {
            $arg1 = $node->args[1]->value;
            if ($arg1 instanceof Node\Expr\Array_) {
                foreach ($arg1->items as $item) {
                    if ($item->value instanceof Node\Expr\ClassConstFetch && $item->value->name->toString() === 'class') {
                        $controller = $this->resolveName($item->value->class);
                    } elseif ($item->value instanceof Node\Scalar\String_) {
                        $controllerMethod = $item->value->value;
                    }
                }
            }
        }
        if ($uri) {
            return [
                'http_method' => strtoupper($httpMethod),
                'uri' => $uri,
                'controller' => $controller,
                'controller_method' => $controllerMethod,
                'line' => $node->getLine()
            ];
        }
        return null;
    }

    // -----------------------------------------------------
    // Enter Node
    // -----------------------------------------------------
    public function enterNode(Node $node) {
        // Route detection (global)
        $route = $this->extractRouteDefinition($node);
        if ($route) $this->routeDefinitions[] = $route;
        $customRoute = $this->extractCustomRouteDefinition($node);
        if ($customRoute) $this->routeDefinitions[] = $customRoute;

        if ($node instanceof Node\Stmt\Namespace_) {
            $this->output["namespace"] = $node->name ? $node->name->toString() : null;
        }

        if ($node instanceof Node\Stmt\Use_) {
            foreach ($node->uses as $use) {
                $this->output["uses"][] = [
                    "name"  => $use->name->toString(),
                    "alias" => $use->alias ? $use->alias->toString() : null
                ];
            }
        }

        if ($node instanceof Node\Expr\Include_) {
            $this->output["includes"][] = [
                "type" => $node->type,
                "file" => $node->expr instanceof Node\Scalar\String_ ? $node->expr->value : null
            ];
        }

        if ($node instanceof Node\Stmt\Function_) {
            $returnType = $node->returnType ? $this->resolveType($node->returnType) : null;
            $this->output["functions"][] = [
                "name"        => $node->name->toString(),
                "param_count" => count($node->params),
                "return_type" => $returnType
            ];
        }

        // ----- Class / Interface / Trait -----
        if ($node instanceof Node\Stmt\Class_) {
            $structure = $this->buildStructureBase($node, "class");
            if ($node->extends) $structure["extends"] = [$this->resolveName($node->extends)];
            foreach ($node->implements as $impl) $structure["implements"][] = $this->resolveName($impl);
            $structure["attributes"] = [];
            foreach ($node->attrGroups as $attrGroup) {
                foreach ($attrGroup->attrs as $attr) {
                    $attrName = $this->resolveName($attr->name);
                    if ($attrName) $structure["attributes"][] = $attrName;
                }
            }
            $this->output["classes"][] = $structure;
            $this->currentStructureIndex = count($this->output["classes"]) - 1;
        }

        if ($node instanceof Node\Stmt\Interface_) {
            $structure = $this->buildStructureBase($node, "interface");
            foreach ($node->extends as $ext) $structure["extends"][] = $this->resolveName($ext);
            $this->output["classes"][] = $structure;
            $this->currentStructureIndex = count($this->output["classes"]) - 1;
        }

        if ($node instanceof Node\Stmt\Trait_) {
            $structure = $this->buildStructureBase($node, "trait");
            $this->output["classes"][] = $structure;
            $this->currentStructureIndex = count($this->output["classes"]) - 1;
        }

        if ($node instanceof Node\Stmt\TraitUse && $this->currentStructureIndex !== null) {
            foreach ($node->traits as $trait) {
                $this->output["classes"][$this->currentStructureIndex]["traits"][] = $this->resolveName($trait);
            }
        }

        if ($node instanceof Node\Stmt\Property && $this->currentStructureIndex !== null) {
            $propType = $this->resolveType($node->type);
            foreach ($node->props as $prop) {
                $this->output["classes"][$this->currentStructureIndex]["properties"][$prop->name->toString()] = $propType;
            }
        }

        // ----- Method -----
        if ($node instanceof Node\Stmt\ClassMethod && $this->currentStructureIndex !== null) {
            $visibility = "public";
            if ($node->isPrivate()) $visibility = "private";
            if ($node->isProtected()) $visibility = "protected";

            $params = [];
            foreach ($node->params as $param) {
                $paramType = $this->resolveType($param->type);
                $params[] = [
                    'name' => $param->var->name,
                    'type' => $paramType
                ];
            }

            $returnType = $node->returnType ? $this->resolveType($node->returnType) : null;

            $method = [
                "name"            => $node->name->toString(),
                "visibility"      => $visibility,
                "params"          => $params,
                "return_type"     => $returnType,
                "calls"           => [],
                "instantiations"  => [],
                "assignments"     => [],
                "function_calls"  => [],
                "sql_strings"     => [],
                "property_fetches"=> [],
                "static_property_fetches" => [],
                "constant_fetches" => [],
                "returns"         => [],
                "has_try_catch"   => false,
                "attributes"      => []
            ];

            foreach ($node->attrGroups as $attrGroup) {
                foreach ($attrGroup->attrs as $attr) {
                    $attrName = $this->resolveName($attr->name);
                    if ($attrName) $method["attributes"][] = $attrName;
                }
            }

            $this->output["classes"][$this->currentStructureIndex]["methods"][] = $method;
            $this->currentMethodIndex = count($this->output["classes"][$this->currentStructureIndex]["methods"]) - 1;
            $this->localVarTypes = [];

            $currentClassFqn = $this->output["classes"][$this->currentStructureIndex]["fqn"];
            if ($currentClassFqn) {
                $this->localVarTypes["this"] = $currentClassFqn;
            }

            // Constructor injection patch
            if (strtolower($node->name->toString()) === '__construct') {
                foreach ($params as $p) {
                    if ($p['type']) {
                        $this->output["classes"][$this->currentStructureIndex]["properties"][$p['name']] = $p['type'];
                    }
                }
            }
        }

        // ----- Parameter (method) -----
        if ($node instanceof Node\Param && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            $paramName = $node->var->name;
            $resolvedType = $this->resolveType($node->type);
            if ($resolvedType) {
                $this->localVarTypes[$paramName] = $resolvedType;
                $this->setNodeType($node->var, $resolvedType);
            }
        }

        // -----------------------------------------------------
        // ASSIGNMENT TRACKING (now emits source_call for exact merging)
        // -----------------------------------------------------
        if ($node instanceof Node\Expr\Assign && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            // Record assignment entry for later merging
            $assignment = null;

            // Case: $var = $obj->method()
            if ($node->var instanceof Node\Expr\Variable && $node->expr instanceof Node\Expr\MethodCall) {
                $varName = $node->var->name;
                $sourceMethod = $node->expr->name instanceof Node\Identifier ? $node->expr->name->toString() : null;
                $assignment = [
                    "var" => $varName,
                    "source_call" => $sourceMethod,
                    "line" => $node->getLine()
                ];
            }
            // Case: $var = Class::staticMethod()
            elseif ($node->var instanceof Node\Expr\Variable && $node->expr instanceof Node\Expr\StaticCall) {
                $varName = $node->var->name;
                $sourceMethod = $node->expr->name instanceof Node\Identifier ? $node->expr->name->toString() : null;
                $assignment = [
                    "var" => $varName,
                    "source_call" => $sourceMethod,
                    "line" => $node->getLine()
                ];
            }
            // Case: $var = func()
            elseif ($node->var instanceof Node\Expr\Variable && $node->expr instanceof Node\Expr\FuncCall) {
                $varName = $node->var->name;
                $sourceFunc = $node->expr->name instanceof Node\Name ? $node->expr->name->toString() : null;
                $assignment = [
                    "var" => $varName,
                    "source_call" => $sourceFunc,
                    "line" => $node->getLine()
                ];
            }
            // Existing: $var = new Class()
            elseif ($node->var instanceof Node\Expr\Variable && $node->expr instanceof Node\Expr\New_) {
                $varName = $node->var->name;
                $class = $this->resolveName($node->expr->class);
                $assignment = [
                    "var" => $varName,
                    "class" => $class,
                    "type" => "instantiation",
                    "line" => $node->getLine()
                ];
            }
            // Existing: $this->prop = ...
            elseif ($node->var instanceof Node\Expr\PropertyFetch &&
                    $node->var->var instanceof Node\Expr\Variable &&
                    $node->var->var->name === "this") {
                if ($node->var->name instanceof Node\Identifier) {
                    $propName = $node->var->name->toString();
                    if ($node->expr instanceof Node\Expr\New_) {
                        $class = $this->resolveName($node->expr->class);
                        $assignment = [
                            "var" => $propName,
                            "class" => $class,
                            "type" => "property_instantiation",
                            "line" => $node->getLine()
                        ];
                    } elseif ($node->expr instanceof Node\Expr\Variable) {
                        $sourceVar = $node->expr->name;
                        $assignment = [
                            "var" => $propName,
                            "source_var" => $sourceVar,
                            "line" => $node->getLine()
                        ];
                    }
                }
            }

            if ($assignment) {
                $this->output["classes"]
                    [$this->currentStructureIndex]
                    ["methods"]
                    [$this->currentMethodIndex]
                    ["assignments"][] = $assignment;
            }

            // Type tracking for local variables
            if ($node->expr instanceof Node\Expr\New_ && $node->var instanceof Node\Expr\Variable) {
                $varName = $node->var->name;
                $resolvedClass = $this->resolveName($node->expr->class);
                if ($resolvedClass) {
                    $this->localVarTypes[$varName] = $resolvedClass;
                    $this->setNodeType($node->var, $resolvedClass);
                    $this->setNodeType($node->expr, $resolvedClass);
                }
            }
            elseif ($node->var instanceof Node\Expr\Variable && $exprType = $this->getNodeType($node->expr)) {
                $varName = $node->var->name;
                $this->localVarTypes[$varName] = $exprType;
                $this->setNodeType($node->var, $exprType);
            }
            // $this->prop = $var (constructor injection)
            if ($node->var instanceof Node\Expr\PropertyFetch &&
                $node->var->var instanceof Node\Expr\Variable &&
                $node->var->var->name === "this" &&
                $node->expr instanceof Node\Expr\Variable &&
                isset($this->localVarTypes[$node->expr->name])) {
                $propName = $node->var->name->toString();
                $this->output["classes"][$this->currentStructureIndex]["properties"][$propName] = $this->localVarTypes[$node->expr->name];
            }
            // $this->service = new ServiceClass()
            if ($node->var instanceof Node\Expr\PropertyFetch &&
                $node->var->var instanceof Node\Expr\Variable &&
                $node->var->var->name === "this" &&
                $node->expr instanceof Node\Expr\New_) {
                if ($node->var->name instanceof Node\Identifier) {
                    $propName = $node->var->name->toString();
                    $resolvedClass = $this->resolveName($node->expr->class);
                    if ($resolvedClass) {
                        $this->output["classes"][$this->currentStructureIndex]["properties"][$propName] = $resolvedClass;
                    }
                }
            }
        }

        // ----- INSTANTIATION -----
        if ($node instanceof Node\Expr\New_ && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            $resolvedClass = $this->resolveName($node->class);
            if ($resolvedClass) {
                $varName = null;
                $parent = $node->getAttribute('parent');
                if ($parent instanceof Node\Expr\Assign) {
                    if ($parent->var instanceof Node\Expr\Variable) $varName = $parent->var->name;
                    elseif ($parent->var instanceof Node\Expr\PropertyFetch &&
                            $parent->var->var instanceof Node\Expr\Variable &&
                            $parent->var->var->name === "this") {
                        if ($parent->var->name instanceof Node\Identifier) $varName = "this->" . $parent->var->name->toString();
                    }
                }
                $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["instantiations"][] = [
                    "var" => $varName,
                    "class" => $resolvedClass,
                    "file" => $this->currentFilePath
                ];
                $this->setNodeType($node, $resolvedClass);
            }
        }

        // -----------------------------------------------------
        // CALLS (use assign_to now, always include line number and file)
        // -----------------------------------------------------
        // ----- STATIC CALL -----
        if ($node instanceof Node\Expr\StaticCall && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            if ($node->name instanceof Node\Identifier) {
                $methodName = $node->name->toString();
                $classNode = $node->class;
                $className = null;
                if ($classNode instanceof Node\Name) {
                    $nameStr = $classNode->toString();
                    if ($nameStr === 'self') {
                        $className = $this->output["classes"][$this->currentStructureIndex]["fqn"];
                    } elseif ($nameStr === 'parent') {
                        $classData = $this->output["classes"][$this->currentStructureIndex];
                        if (!empty($classData["extends"])) $className = $classData["extends"][0];
                    } else {
                        $className = $this->resolveName($classNode);
                    }
                }

                // Detect assignment target
                $assignTo = null;
                $parent = $node->getAttribute('parent');
                if ($parent instanceof Node\Expr\Assign && $parent->expr === $node) {
                    if ($parent->var instanceof Node\Expr\Variable) {
                        $assignTo = $parent->var->name;
                    } elseif ($parent->var instanceof Node\Expr\PropertyFetch &&
                              $parent->var->var instanceof Node\Expr\Variable &&
                              $parent->var->var->name === "this") {
                        $assignTo = "this->" . $parent->var->name->toString();
                    }
                }

                // Facade resolution
                if ($className && isset($this->facadeMap[$className])) {
                    $fqcnFacade = $this->facadeMap[$className];
                    $call = [
                        "type"      => "method",
                        "target"    => $fqcnFacade,
                        "method"    => $methodName,
                        "line"      => $node->getLine(),
                        "file"      => $this->currentFilePath
                    ];
                    if ($assignTo) $call["assign_to"] = $assignTo;
                    $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["calls"][] = $call;
                } else {
                    $call = [
                        "type"   => "method",
                        "target" => $className,
                        "method" => $methodName,
                        "line"   => $node->getLine(),
                        "file"   => $this->currentFilePath
                    ];
                    if ($assignTo) $call["assign_to"] = $assignTo;
                    $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["calls"][] = $call;

                    // Service locator: get/make/resolve
                    if (in_array(strtolower($methodName), ['get', 'make', 'resolve']) && isset($node->args[0])) {
                        $arg = $node->args[0]->value;
                        if ($arg instanceof Node\Expr\ClassConstFetch && $arg->name->toString() === 'class') {
                            $targetClass = $this->resolveName($arg->class);
                            if ($targetClass) $this->setNodeType($node, $targetClass);
                        }
                    }
                    // ORM heuristic
                    if (in_array(strtolower($methodName), ['query', 'newquery', 'builder'])) {
                        $this->setNodeType($node, $className);
                    }
                }
                if ($className && !$this->getNodeType($node)) {
                    $this->setNodeType($node, $className);
                }
            }
        }

        // ----- FUNCTION CALL -----
        if ($node instanceof Node\Expr\FuncCall && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            if ($node->name instanceof Node\Name) {
                $funcName = $node->name->toString();
                $assignTo = null;
                $parent = $node->getAttribute('parent');
                if ($parent instanceof Node\Expr\Assign && $parent->expr === $node) {
                    if ($parent->var instanceof Node\Expr\Variable) {
                        $assignTo = $parent->var->name;
                    } elseif ($parent->var instanceof Node\Expr\PropertyFetch &&
                              $parent->var->var instanceof Node\Expr\Variable &&
                              $parent->var->var->name === "this") {
                        $assignTo = "this->" . $parent->var->name->toString();
                    }
                }
                $call = [
                    "name" => $funcName,
                    "line" => $node->getLine(),
                    "file" => $this->currentFilePath
                ];
                if ($assignTo) $call["assign_to"] = $assignTo;
                $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["function_calls"][] = $call;

                // container helper
                if (in_array($funcName, ['app', 'resolve']) && isset($node->args[0])) {
                    $arg = $node->args[0]->value;
                    if ($arg instanceof Node\Expr\ClassConstFetch && $arg->name->toString() === 'class') {
                        $targetClass = $this->resolveName($arg->class);
                        if ($targetClass) $this->setNodeType($node, $targetClass);
                    }
                }
            }
        }

        // ----- METHOD CALL (CRITICAL FIX: always populate target when possible, now includes file) -----
        if ($node instanceof Node\Expr\MethodCall && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            if ($node->name instanceof Node\Identifier) {
                $methodName = $node->name->toString();
                $targetClass = null;
                $objectName = null;

                $varType = $this->getNodeType($node->var);
                if ($varType) $targetClass = $varType;

                if ($node->var instanceof Node\Expr\Variable) {
                    $objectName = $node->var->name;
                } elseif ($node->var instanceof Node\Expr\PropertyFetch &&
                          $node->var->var instanceof Node\Expr\Variable &&
                          $node->var->var->name === "this") {
                    $objectName = $node->var->name->toString();
                }

                if (!$targetClass) {
                    if ($node->var instanceof Node\Expr\PropertyFetch &&
                        $node->var->var instanceof Node\Expr\Variable &&
                        $node->var->var->name === "this") {
                        $propertyName = $node->var->name->toString();
                        $classData = $this->output["classes"][$this->currentStructureIndex];
                        if (isset($classData["properties"][$propertyName])) {
                            $targetClass = $classData["properties"][$propertyName];
                        }
                    } elseif ($node->var instanceof Node\Expr\Variable) {
                        $varNameObj = $node->var->name;
                        if (isset($this->localVarTypes[$varNameObj])) {
                            $targetClass = $this->localVarTypes[$varNameObj];
                        }
                    }
                }

                // Container detection ($this->app->make/get...)
                if (in_array(strtolower($methodName), ['make', 'get', 'resolve']) &&
                    $node->var instanceof Node\Expr\PropertyFetch &&
                    $node->var->var instanceof Node\Expr\Variable &&
                    $node->var->var->name === 'this' &&
                    $node->var->name instanceof Node\Identifier &&
                    $node->var->name->toString() === 'app') {
                    if (isset($node->args[0])) {
                        $arg = $node->args[0]->value;
                        if ($arg instanceof Node\Expr\ClassConstFetch && $arg->name->toString() === 'class') {
                            $targetClass = $this->resolveName($arg->class);
                            if ($targetClass) $this->setNodeType($node, $targetClass);
                        }
                    }
                }

                // Detect assignment target
                $assignTo = null;
                $parent = $node->getAttribute('parent');
                if ($parent instanceof Node\Expr\Assign && $parent->expr === $node) {
                    if ($parent->var instanceof Node\Expr\Variable) {
                        $assignTo = $parent->var->name;
                    } elseif ($parent->var instanceof Node\Expr\PropertyFetch &&
                              $parent->var->var instanceof Node\Expr\Variable &&
                              $parent->var->var->name === "this") {
                        $assignTo = "this->" . $parent->var->name->toString();
                    }
                }

                // 🔥 CRITICAL FIX: If targetClass is still not found, try to resolve
                // $this->property->method() by looking at the class's properties
                if (!$targetClass && $objectName) {
                    $classData = $this->output["classes"][$this->currentStructureIndex];
                    if (isset($classData["properties"][$objectName])) {
                        $targetClass = $classData["properties"][$objectName];
                    }
                }

                $call = [
                    "type"   => "method",
                    "method" => $methodName,
                    "object" => $objectName,
                    "line"   => $node->getLine(),
                    "file"   => $this->currentFilePath
                ];
                if ($targetClass) $call["target"] = $targetClass;
                if ($assignTo) $call["assign_to"] = $assignTo;

                $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["calls"][] = $call;

                // Fluent chain propagation (non-terminal methods)
                if ($targetClass) {
                    $terminalMethods = ['get','first','find','count','exists','pluck','paginate','chunk','cursor','value','sum','avg'];
                    if (!in_array(strtolower($methodName), $terminalMethods)) {
                        $this->setNodeType($node, $targetClass);
                    }
                }
            }
        }

        // ----- STATIC PROPERTY FETCH -----
        if ($node instanceof Node\Expr\StaticPropertyFetch && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            if ($node->name instanceof Node\Identifier) {
                $propName = $node->name->toString();
                $className = null;
                if ($node->class instanceof Node\Name) {
                    $nameStr = $node->class->toString();
                    if ($nameStr === 'self') $className = $this->output["classes"][$this->currentStructureIndex]["fqn"];
                    elseif ($nameStr === 'parent') {
                        $classData = $this->output["classes"][$this->currentStructureIndex];
                        if (!empty($classData["extends"])) $className = $classData["extends"][0];
                    } else $className = $this->resolveName($node->class);
                }
                $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["static_property_fetches"][] = [
                    'class' => $className,
                    'property' => $propName
                ];
            }
        }

        // ----- CLASS CONST FETCH -----
        if ($node instanceof Node\Expr\ClassConstFetch && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            $constName = $node->name->toString();
            $className = null;
            if ($node->class instanceof Node\Name) {
                $nameStr = $node->class->toString();
                if ($nameStr === 'self') $className = $this->output["classes"][$this->currentStructureIndex]["fqn"];
                elseif ($nameStr === 'parent') {
                    $classData = $this->output["classes"][$this->currentStructureIndex];
                    if (!empty($classData["extends"])) $className = $classData["extends"][0];
                } else $className = $this->resolveName($node->class);
            }
            $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["constant_fetches"][] = [
                'class' => $className,
                'constant' => $constName
            ];
        }

        // ----- PROPERTY FETCH ($this->property) -----
        if ($node instanceof Node\Expr\PropertyFetch && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            if ($node->var instanceof Node\Expr\Variable && $node->var->name === "this") {
                if (!$node->name instanceof Node\Identifier) return;
                $propertyName = $node->name->toString();
                $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["property_fetches"][] = $propertyName;

                $classData = $this->output["classes"][$this->currentStructureIndex];
                if (isset($classData["properties"][$propertyName])) {
                    $this->setNodeType($node, $classData["properties"][$propertyName]);
                } else {
                    // Fallback: look in constructor param type
                    if (isset($this->localVarTypes[$propertyName])) {
                        $this->output["classes"][$this->currentStructureIndex]["properties"][$propertyName] = $this->localVarTypes[$propertyName];
                        $this->setNodeType($node, $this->localVarTypes[$propertyName]);
                    }
                }
            }
        }

        // ----- RETURN -----
        if ($node instanceof Node\Stmt\Return_ && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            $returnInfo = ['expr' => null];
            if ($node->expr) {
                $exprType = $this->getNodeType($node->expr);
                if ($exprType) $returnInfo['type'] = $exprType;
                if ($node->expr instanceof Node\Expr\Variable) {
                    $returnInfo['expr'] = '$' . $node->expr->name;
                } elseif ($node->expr instanceof Node\Expr\PropertyFetch) {
                    $returnInfo['expr'] = '$this->' . $node->expr->name->toString();
                } elseif ($node->expr instanceof Node\Expr\StaticPropertyFetch) {
                    $className = $node->expr->class instanceof Node\Name ? $node->expr->class->toString() : '?';
                    $propName = $node->expr->name->toString();
                    $returnInfo['expr'] = $className . '::$' . $propName;
                } elseif ($node->expr instanceof Node\Scalar\String_) {
                    $returnInfo['expr'] = '"' . $node->expr->value . '"';
                } elseif ($node->expr instanceof Node\Expr\New_) {
                    $returnInfo['expr'] = 'new ' . ($node->expr->class instanceof Node\Name ? $node->expr->class->toString() : '?');
                } else {
                    $returnInfo['expr'] = get_class($node->expr);
                }
            }
            $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["returns"][] = $returnInfo;
        }

        // ----- TRY/CATCH -----
        if ($node instanceof Node\Stmt\TryCatch && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["has_try_catch"] = true;
        }

        // ----- SQL Strings -----
        if ($node instanceof Node\Scalar\String_ && $this->currentStructureIndex !== null && $this->currentMethodIndex !== null) {
            $value = $node->value;
            if (preg_match('/\b(SELECT|INSERT|UPDATE|DELETE)\b/i', $value)) {
                $this->output["classes"][$this->currentStructureIndex]["methods"][$this->currentMethodIndex]["sql_strings"][] = $value;
            }
        }
    }

    // -----------------------------------------------------
    // Leave Node
    // -----------------------------------------------------
    public function leaveNode(Node $node) {
        if ($node instanceof Node\Stmt\ClassMethod) {
            $this->currentMethodIndex = null;
        }
        if ($node instanceof Node\Stmt\Class_ || $node instanceof Node\Stmt\Interface_ || $node instanceof Node\Stmt\Trait_) {
            $this->currentStructureIndex = null;
        }
    }
}

// ----- Parse All Files -----
$allResults = [];
foreach ($files as $filePath) {
    $code = file_get_contents($filePath);
    $loc = substr_count($code, "\n") + 1;
    $hash = md5($code);

    $result = [
        "file"      => $filePath,
        "loc"       => $loc,
        "hash"      => $hash,
        "namespace" => null,
        "uses"      => [],
        "classes"   => [],
        "functions" => [],
        "includes"  => [],
        "error"     => false
    ];

    try {
        $ast = $parser->parse($code);
        if ($ast) {
            $traverser = new NodeTraverser();
            $traverser->addVisitor(new ParentConnectingVisitor());
            $traverser->addVisitor(new NameResolver());
            $astVisitor = new GenericASTVisitor($result, $filePath);  // 🔥 gunakan class yang sudah direname
            $traverser->addVisitor($astVisitor);
            $traverser->traverse($ast);

            // Inject route definitions as virtual functions
            $routes = $astVisitor->getRouteDefinitions();
            foreach ($routes as $route) {
                $result["functions"][] = [
                    "name" => $route['http_method'] . ' ' . $route['uri'],
                    "fqn"  => "route::" . strtolower($route['http_method']) . "::" . $route['uri'],
                    "type" => "route",
                    "http_method" => $route['http_method'],
                    "uri"         => $route['uri'],
                    "controller"  => $route['controller'],
                    "controller_method" => $route['controller_method'],
                    "line" => $route['line'],
                    "calls" => []
                ];
                if ($route['controller'] && $route['controller_method']) {
                    $result["functions"][count($result["functions"]) - 1]["calls"][] = [
                        "type"   => "method",
                        "target" => $route['controller'],
                        "method" => $route['controller_method']
                    ];
                }
            }
        }
    } catch (Error $e) {
        $result["error"] = true;
        $result["message"] = $e->getMessage();
    }

    $allResults[] = $result;
}

echo json_encode($allResults, JSON_PRETTY_PRINT);
exit(0);