""""
setup.py — Meilisearch index creation + settings for jobs / users / companies.
"""

from __future__ import annotations

import argparse
import os
import time
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

MEILI_URL = os.getenv("MEILI_URL", "http://localhost:7700")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY", "masterKey123")
HEADERS = {"Authorization": f"Bearer {MEILI_KEY}"}

INDEX_CONFIGS: Dict[str, Dict[str, Any]] = {
    "jobs": {
        "primaryKey": "id",
        "searchableAttributes": [
            "job_title",
            "job_title_compact",
            "tag",
            "skill_names",
            "department_name",
            "designation_name",
            "role_type_name",
            "job_mode_name",
            "experience_name",
            "salary_name",
            "industry_name",
            "company_name",
            "city_name",
            "state_name",
            "country_name",
            "job_description",
            "roles_responsibility",
        ],
        "filterableAttributes": [
            "company_id",
            "industry_id",
            "department",
            "designation",
            "experience",
            "role_type",
            "job_mode",
            "country",
            "state",
            "city",
            "urgent",
            "vacancy",
            "salary",
            "skill_ids",
            "benefit_ids",
            "applicant_count",
            "create_ts",
            "posted_date",
            "closing_date",
        ],
        "sortableAttributes": [
            "create_ts",
            "posted_date",
            "closing_date",
            "salary",
            "urgent",
            "applicant_count",
        ],
        "rankingRules": [
            "words",
            "typo",
            "proximity",
            "attribute",
            "sort",
            "exactness",
        ],
        "typoTolerance": {
            "enabled": True,
            "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
            "disableOnAttributes": ["company_name", "tag"],
        },
        "proximityPrecision": "byWord",
        "nonSeparatorTokens": [".", "+", "#", "@"],
        "stopWords": ["a", "an", "the", "in", "at", "for", "of", "and", "or", "with", "to", "is", "are"],
        "synonyms": {
            "js": ["javascript"], "javascript": ["js"],
            "ts": ["typescript"], "typescript": ["ts"],
            "node": ["nodejs", "node.js"], "nodejs": ["node", "node.js"],
            "react": ["reactjs", "react.js"], "reactjs": ["react", "react.js"],
            "py": ["python"],
            "fe": ["frontend", "front-end", "front end"],
            "be": ["backend", "back-end", "back end"],
            "k8s": ["kubernetes"],
            "frontend": ["front-end", "front end", "ui"],
            "backend": ["back-end", "back end"],
            "fullstack": ["full-stack", "full stack"],
            "devops": ["dev ops", "sre", "site reliability"],
            "ml": ["machine learning"],
            "ai": ["artificial intelligence"],
            "qa": ["quality assurance", "testing"],
            "hr": ["human resources"],
            "pm": ["project manager", "product manager"],
            "ui": ["user interface"],
            "ux": ["user experience"],
            "dba": ["database administrator"],
            "sde": ["software development engineer", "software engineer"],
            "swe": ["software engineer"],
            "ds": ["data science", "data scientist"],
            "dl": ["deep learning"],
            "nlp": ["natural language processing"],
            "cv": ["computer vision"],
            "aws": ["amazon web services"],
            "gcp": ["google cloud platform"],
            "sql": ["structured query language"],
            "nosql": ["no sql"],
            "dotnet": [".net", "dot net"],
            "csharp": ["c#"],
            "cpp": ["c++"],
            "golang": ["go"],
            "reactnative": ["react native"],
            "nextjs": ["next.js", "next js"],
            "vuejs": ["vue.js", "vue js", "vue"],
            "angularjs": ["angular.js", "angular"],
        },
        "displayedAttributes": ["*"],
        "pagination": {"maxTotalHits": 5000},
    },

    "users": {
        "primaryKey": "id",
        "searchableAttributes": [
            "full_name",
            "full_name_compact",
            "ccid",
            "skill_names",
            "industry_name",
           #"current_company_name", currently disabled for future subscription
            "current_position_name",
            "work_status_name",
            "city_name",
            "state_name",
            "country_name",
            "email",
        ],
        "filterableAttributes": [
            # industry_id = current company's industry (matches PHP cmp.industry)
            "industry_id",
            "user_industry_id",
            "country",
            "state",
            "city",
            "skill_ids",

            "work_status",
            "current_company",
            "current_possition",
            "on_immediate",
            "on_notice",

            "exp_department",
            "exp_employment_type",
            "exp_salary",
            "verified_employement",
            "verified_salary",
            "verified_identity",

            "star_rating_avg",
            "total_experience_years",
            "percentage",

            # education filters
            "education_course_ids",
            "education_course_type_ids",
        ],
        "sortableAttributes": [
            "percentage",
            "star_rating_avg",
            "total_experience_years",
            "create_date",
	    "rank_score",
        ],
        "rankingRules": [
            "words",
            "typo",
            "proximity",
            "attribute",
	    "rank_score:desc",
            "sort",
            "exactness",
        ],
        "typoTolerance": {
            "enabled": True,
            "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
            "disableOnAttributes": ["ccid", "individual_id", "email", "phone", "ccid_numeric"],
        },
        "proximityPrecision": "byWord",
        "nonSeparatorTokens": [".", "+", "#", "@"],
        "separatorTokens": ["cce", "ccc"],
        "stopWords": ["a", "an", "the", "and", "or"],
        "synonyms": {
            "sde": ["software development engineer", "software engineer"],
            "swe": ["software engineer"],
            "frontend": ["front-end", "front end"],
            "backend": ["back-end", "back end"],
            "fullstack": ["full-stack", "full stack"],
            "hr": ["human resources"],
            "pm": ["project manager", "product manager"],
        },
        "displayedAttributes": ["*"],
        "pagination": {"maxTotalHits": 2000},
    },

    "companies": {
        "primaryKey": "id",
        "searchableAttributes": [
            "full_name",
            "full_name_compact",
            "ccid",
            "industry_name",
            "city_name",
            "state_name",
            "country_name",
            "email",
        ],
        "filterableAttributes": [
            "industry_id",
            "country",
            "state",
            "city",
            "benefit_ids",
            "job_mode_ids",
            "last_job_create_ts",
            "is_verified_company",
        ],
        "sortableAttributes": [
            "create_date",
            "last_job_create_ts",
	    "rank_score",
        ],
        "rankingRules": [
            "words",
            "typo",
            "proximity",
            "attribute",
	    "rank_score:desc",
            "sort",
            "exactness",
        ],
        "typoTolerance": {
            "enabled": True,
            "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 9},
            "disableOnAttributes": ["email", "phone", "ccid", "individual_id", "ccid_numeric"],
        },
        "proximityPrecision": "byWord",
        "nonSeparatorTokens": [".", "+", "#", "@"],
        "separatorTokens": ["cce", "ccc"],
        "stopWords": ["a", "an", "the", "and", "or", "pvt", "ltd", "llc", "inc"],
	"synonyms": {
    # ── Programming Languages ──────────────────────────────────────
    "js":         ["javascript"],
    "javascript": ["js"],
    "ts":         ["typescript"],
    "typescript": ["ts"],
    "py":         ["python"],
    "python":     ["py"],
    "rb":         ["ruby"],
    "golang":     ["go"],
    "go":         ["golang"],
    "csharp":     ["c#", "dotnet", ".net"],
    "c#":         ["csharp", "dotnet", ".net"],
    "dotnet":     [".net", "c#", "csharp", "dot net"],
    ".net":       ["dotnet", "csharp", "c#"],
    "cpp":        ["c++"],
    "c++":        ["cpp"],
    "kotlin":     ["android development"],
    "swift":      ["ios development"],
    "rust":       ["systems programming"],
    "scala":      ["functional programming", "jvm"],
    "perl":       ["scripting"],
    "lua":        ["scripting"],
    "r":          ["data analysis", "statistics"],
    "matlab":     ["numerical computing", "scientific computing"],
    "cobol":      ["legacy systems", "mainframe"],
    "fortran":    ["scientific computing", "hpc"],
    "haskell":    ["functional programming"],
    "erlang":     ["distributed systems", "telecoms"],
    "elixir":     ["phoenix", "functional programming"],
    "clojure":    ["functional programming", "lisp"],
    "groovy":     ["jvm", "gradle"],
    "dart":       ["flutter"],
    "flutter":    ["dart", "cross platform mobile"],
    "solidity":   ["smart contracts", "blockchain", "ethereum", "web3"],
    "assembly":   ["asm", "low level programming"],
    "asm":        ["assembly", "low level"],

    # ── Web Frameworks & Libraries ─────────────────────────────────
    "react":       ["reactjs", "react.js"],
    "reactjs":     ["react", "react.js"],
    "react.js":    ["react", "reactjs"],
    "vue":         ["vuejs", "vue.js"],
    "vuejs":       ["vue", "vue.js"],
    "vue.js":      ["vue", "vuejs"],
    "angular":     ["angularjs", "angular.js"],
    "angularjs":   ["angular", "angular.js"],
    "nextjs":      ["next.js", "next js"],
    "next.js":     ["nextjs", "next js"],
    "nuxt":        ["nuxtjs", "nuxt.js"],
    "svelte":      ["sveltekit"],
    "sveltekit":   ["svelte"],
    "django":      ["python web", "drf"],
    "flask":       ["python web", "microframework"],
    "fastapi":     ["python api", "async python"],
    "express":     ["expressjs", "node web"],
    "expressjs":   ["express", "node web"],
    "nestjs":      ["nest.js", "node framework"],
    "spring":      ["spring boot", "java web"],
    "springboot":  ["spring boot", "spring", "java web"],
    "spring boot": ["springboot", "spring", "java"],
    "rails":       ["ruby on rails", "ror"],
    "ror":         ["rails", "ruby on rails"],
    "laravel":     ["php framework", "php web"],
    "symfony":     ["php framework"],
    "codeigniter": ["php framework"],
    "asp.net":     ["aspnet", "dotnet web", "c# web"],
    "aspnet":      ["asp.net", "dotnet web"],
    "gatsby":      ["gatsby.js", "react static"],
    "remix":       ["remix.js", "react framework"],
    "htmx":        ["hypermedia", "html"],
    "jquery":      ["javascript library"],
    "backbone":    ["backbone.js", "javascript mvc"],
    "ember":       ["ember.js", "javascript framework"],

    # ── Mobile ────────────────────────────────────────────────────
    "reactnative":    ["react native", "cross platform mobile"],
    "react native":   ["reactnative", "cross platform mobile"],
    "ios":            ["swift", "objective-c", "apple development", "xcode"],
    "android":        ["kotlin", "java mobile", "android studio"],
    "xamarin":        ["cross platform mobile", "dotnet mobile"],
    "ionic":          ["cross platform mobile", "hybrid app"],
    "cordova":        ["phonegap", "hybrid app"],
    "phonegap":       ["cordova", "hybrid app"],
    "maui":           [".net maui", "dotnet mobile", "cross platform"],
    "capacitor":      ["ionic", "cross platform"],

    # ── Frontend ───────────────────────────────────────────────────
    "fe":         ["frontend", "front-end", "front end"],
    "frontend":   ["front-end", "front end", "fe", "ui development"],
    "front-end":  ["frontend", "front end", "fe"],
    "ui":         ["user interface", "frontend", "ux"],
    "ux":         ["user experience", "product design", "ui"],
    "css":        ["styling", "sass", "scss", "tailwind"],
    "sass":       ["scss", "css preprocessor"],
    "scss":       ["sass", "css preprocessor"],
    "tailwind":   ["tailwindcss", "utility css"],
    "tailwindcss":["tailwind", "utility css"],
    "bootstrap":  ["css framework", "ui framework"],
    "mui":        ["material ui", "material design"],
    "shadcn":     ["shadcn ui", "react components"],
    "figma":      ["ui design", "prototyping", "design tool"],
    "sketch":     ["ui design", "prototyping"],
    "adobe xd":   ["ui design", "prototyping"],
    "webpack":    ["bundler", "build tool"],
    "vite":       ["build tool", "frontend tooling"],
    "babel":      ["transpiler", "javascript tooling"],
    "storybook":  ["component library", "ui development"],
    "threejs":    ["three.js", "webgl", "3d web"],
    "three.js":   ["threejs", "webgl", "3d"],
    "webgl":      ["3d graphics", "threejs"],
    "wasm":       ["webassembly"],
    "webassembly":["wasm"],
    "pwa":        ["progressive web app"],

    # ── Backend ────────────────────────────────────────────────────
    "be":         ["backend", "back-end", "back end"],
    "backend":    ["back-end", "back end", "server side", "be"],
    "back-end":   ["backend", "back end", "server side"],
    "api":        ["rest api", "graphql", "web services"],
    "rest":       ["rest api", "restful", "web services"],
    "restful":    ["rest", "rest api"],
    "graphql":    ["gql", "api query language"],
    "gql":        ["graphql"],
    "grpc":       ["rpc", "protobuf", "protocol buffers"],
    "protobuf":   ["protocol buffers", "grpc"],
    "websocket":  ["ws", "realtime", "socket.io"],
    "socket.io":  ["websocket", "realtime"],
    "rabbitmq":   ["message queue", "amqp", "messaging"],
    "kafka":      ["event streaming", "message queue", "apache kafka"],
    "celery":     ["task queue", "python async", "distributed tasks"],
    "redis":      ["cache", "in-memory db", "pub sub"],
    "nginx":      ["web server", "reverse proxy", "load balancer"],
    "apache":     ["web server", "httpd"],
    "gunicorn":   ["python server", "wsgi"],
    "uvicorn":    ["python server", "asgi", "async python"],

    # ── Databases ─────────────────────────────────────────────────
    "sql":        ["structured query language", "relational database", "rdbms"],
    "nosql":      ["no sql", "non relational", "document db"],
    "mysql":      ["relational database", "sql", "mariadb"],
    "mariadb":    ["mysql", "relational database", "sql"],
    "postgres":   ["postgresql", "postgres", "relational database"],
    "postgresql": ["postgres", "relational database", "sql"],
    "mssql":      ["sql server", "microsoft sql", "t-sql"],
    "sql server": ["mssql", "microsoft sql"],
    "oracle":     ["oracle db", "pl/sql", "enterprise database"],
    "sqlite":     ["embedded database", "lightweight sql"],
    "mongodb":    ["mongo", "nosql", "document database"],
    "mongo":      ["mongodb", "nosql"],
    "cassandra":  ["apache cassandra", "wide column", "nosql"],
    "dynamodb":   ["aws dynamodb", "nosql", "serverless db"],
    "firestore":  ["firebase", "google cloud db", "nosql"],
    "couchdb":    ["nosql", "document database"],
    "neo4j":      ["graph database", "cypher"],
    "influxdb":   ["time series database", "tsdb"],
    "timescaledb":["time series", "postgres extension"],
    "elasticsearch":["elastic", "search engine", "elk"],
    "elastic":    ["elasticsearch", "elk", "search"],
    "meilisearch":["search engine", "full text search"],
    "solr":       ["apache solr", "search engine"],
    "supabase":   ["postgres", "firebase alternative", "baaS"],
    "planetscale":["mysql", "serverless database"],
    "cockroachdb":["distributed sql", "newSQL"],

    # ── Cloud & Infrastructure ─────────────────────────────────────
    "aws":        ["amazon web services", "cloud", "amazon cloud"],
    "gcp":        ["google cloud platform", "google cloud"],
    "azure":      ["microsoft azure", "microsoft cloud"],
    "cloud":      ["aws", "gcp", "azure", "cloud computing"],
    "serverless": ["lambda", "cloud functions", "faas"],
    "lambda":     ["aws lambda", "serverless", "faas"],
    "ec2":        ["aws ec2", "virtual machine", "cloud server"],
    "s3":         ["aws s3", "object storage", "blob storage"],
    "rds":        ["aws rds", "managed database", "cloud database"],
    "eks":        ["kubernetes", "aws kubernetes"],
    "gke":        ["kubernetes", "google kubernetes"],
    "aks":        ["kubernetes", "azure kubernetes"],
    "cloudflare": ["cdn", "edge network", "ddos protection"],
    "vercel":     ["deployment", "frontend hosting", "nextjs hosting"],
    "netlify":    ["deployment", "frontend hosting", "jamstack"],
    "heroku":     ["paas", "cloud platform", "deployment"],
    "digitalocean":["cloud", "vps", "droplets"],
    "linode":     ["cloud", "vps", "akamai cloud"],
    "vultr":      ["cloud", "vps"],

    # ── DevOps & CI/CD ────────────────────────────────────────────
    "devops":     ["dev ops", "sre", "site reliability", "platform engineering"],
    "sre":        ["site reliability engineering", "devops"],
    "k8s":        ["kubernetes", "container orchestration"],
    "kubernetes": ["k8s", "container orchestration", "helm"],
    "docker":     ["containerization", "containers"],
    "helm":       ["kubernetes package manager", "k8s"],
    "terraform":  ["iac", "infrastructure as code", "hcl"],
    "iac":        ["infrastructure as code", "terraform", "ansible", "pulumi"],
    "ansible":    ["configuration management", "automation", "iac"],
    "puppet":     ["configuration management", "automation"],
    "chef":       ["configuration management", "automation"],
    "pulumi":     ["iac", "infrastructure as code"],
    "jenkins":    ["ci cd", "continuous integration", "build automation"],
    "github actions":["ci cd", "github ci", "continuous integration"],
    "gitlab ci":  ["ci cd", "continuous integration", "gitlab"],
    "circleci":   ["ci cd", "continuous integration"],
    "travis":     ["travis ci", "ci cd"],
    "argo":       ["argocd", "gitops", "kubernetes cd"],
    "argocd":     ["argo", "gitops", "kubernetes"],
    "gitops":     ["argocd", "flux", "kubernetes cd"],
    "prometheus": ["monitoring", "metrics", "observability"],
    "grafana":    ["monitoring", "dashboards", "observability"],
    "elk":        ["elasticsearch", "logstash", "kibana", "logging"],
    "datadog":    ["monitoring", "observability", "apm"],
    "newrelic":   ["monitoring", "apm", "observability"],
    "splunk":     ["logging", "monitoring", "siem"],
    "pagerduty":  ["incident management", "on-call"],
    "vault":      ["hashicorp vault", "secrets management"],
    "consul":     ["service mesh", "service discovery"],
    "istio":      ["service mesh", "kubernetes networking"],
    "linkerd":    ["service mesh"],
    "linux":      ["unix", "ubuntu", "centos", "rhel", "debian"],
    "unix":       ["linux", "posix"],
    "bash":       ["shell scripting", "sh", "zsh"],
    "powershell": ["windows scripting", "ps", "windows automation"],

    # ── Data Science & ML/AI ──────────────────────────────────────
    "ml":         ["machine learning", "ai", "artificial intelligence"],
    "ai":         ["artificial intelligence", "machine learning", "deep learning"],
    "dl":         ["deep learning", "neural networks", "ml"],
    "nlp":        ["natural language processing", "text ai", "llm"],
    "cv":         ["computer vision", "image recognition", "object detection"],
    "llm":        ["large language model", "nlp", "gpt", "generative ai"],
    "genai":      ["generative ai", "llm", "gpt", "ai"],
    "generative ai":["genai", "llm", "gpt", "stable diffusion"],
    "ds":         ["data science", "data scientist", "analytics"],
    "data science":["ds", "machine learning", "analytics", "statistics"],
    "mlops":      ["ml engineering", "model deployment", "devops ml"],
    "tensorflow": ["tf", "deep learning", "keras"],
    "tf":         ["tensorflow", "deep learning"],
    "keras":      ["tensorflow", "deep learning"],
    "pytorch":    ["torch", "deep learning", "ml framework"],
    "torch":      ["pytorch", "deep learning"],
    "sklearn":    ["scikit-learn", "machine learning", "python ml"],
    "scikit-learn":["sklearn", "machine learning"],
    "pandas":     ["data analysis", "python data", "dataframe"],
    "numpy":      ["numerical computing", "python data"],
    "scipy":      ["scientific computing", "python data"],
    "matplotlib": ["data visualization", "python charts"],
    "seaborn":    ["data visualization", "python charts"],
    "plotly":     ["interactive charts", "data visualization"],
    "spark":      ["apache spark", "big data", "pyspark"],
    "pyspark":    ["spark", "apache spark", "big data"],
    "hadoop":     ["big data", "hdfs", "mapreduce"],
    "hive":       ["big data sql", "hadoop"],
    "airflow":    ["apache airflow", "data pipeline", "workflow orchestration"],
    "dbt":        ["data build tool", "data transformation", "analytics engineering"],
    "dask":       ["parallel computing", "big data python"],
    "ray":        ["distributed computing", "ml scaling"],
    "huggingface":["transformers", "nlp", "llm", "ml models"],
    "transformers":["huggingface", "nlp", "bert", "gpt"],
    "bert":       ["nlp", "language model", "transformers"],
    "gpt":        ["llm", "openai", "language model", "chatgpt"],
    "openai":     ["gpt", "chatgpt", "llm"],
    "langchain":  ["llm framework", "ai agents", "rag"],
    "rag":        ["retrieval augmented generation", "llm", "vector search"],
    "vector db":  ["pinecone", "weaviate", "chroma", "embeddings"],
    "pinecone":   ["vector database", "embeddings", "rag"],
    "weaviate":   ["vector database", "embeddings"],
    "faiss":      ["vector search", "similarity search", "embeddings"],
    "tableau":    ["data visualization", "bi", "business intelligence"],
    "powerbi":    ["power bi", "microsoft bi", "data visualization"],
    "power bi":   ["powerbi", "microsoft bi", "business intelligence"],
    "looker":     ["bi", "business intelligence", "data visualization"],
    "metabase":   ["bi", "business intelligence", "analytics"],
    "superset":   ["apache superset", "bi", "data visualization"],
    "snowflake":  ["cloud data warehouse", "data warehouse"],
    "bigquery":   ["google bigquery", "cloud data warehouse", "gcp data"],
    "redshift":   ["aws redshift", "data warehouse"],
    "databricks": ["spark", "data lakehouse", "ml platform"],
    "datalake":   ["data lake", "s3", "hdfs", "big data storage"],
    "etl":        ["data pipeline", "data integration", "extract transform load"],
    "elt":        ["data pipeline", "data integration", "reverse etl"],

    # ── Security ──────────────────────────────────────────────────
    "appsec":     ["application security", "security engineering"],
    "infosec":    ["information security", "cybersecurity"],
    "cybersecurity":["infosec", "security", "network security"],
    "pentesting": ["penetration testing", "ethical hacking", "red team"],
    "pentest":    ["penetration testing", "ethical hacking"],
    "vapt":       ["vulnerability assessment", "penetration testing"],
    "soc":        ["security operations center", "threat monitoring"],
    "siem":       ["security information", "splunk", "log management"],
    "iam":        ["identity access management", "authentication", "authorization"],
    "oauth":      ["authentication", "authorization", "sso"],
    "sso":        ["single sign on", "oauth", "saml"],
    "saml":       ["sso", "authentication", "federation"],
    "jwt":        ["json web token", "authentication", "api auth"],
    "devsecops":  ["security devops", "secure sdlc", "shift left security"],
    "grc":        ["governance risk compliance", "compliance", "risk management"],
    "iso27001":   ["information security standard", "isms", "compliance"],
    "soc2":       ["security compliance", "audit", "trust services"],
    "gdpr":       ["data privacy", "data protection", "compliance"],
    "dlp":        ["data loss prevention", "data security"],
    "waf":        ["web application firewall", "ddos protection"],
    "ids":        ["intrusion detection", "network security"],
    "ips":        ["intrusion prevention", "network security"],
    "vpn":        ["virtual private network", "network security"],
    "zero trust": ["zero trust network", "ztna", "security model"],

    # ── Networking ─────────────────────────────────────────────────
    "ccna":       ["cisco", "networking certification", "network engineer"],
    "ccnp":       ["cisco", "networking certification"],
    "ccie":       ["cisco", "expert networking"],
    "sd-wan":     ["software defined wan", "network virtualization"],
    "sdn":        ["software defined networking"],
    "noc":        ["network operations", "network monitoring"],
    "bgp":        ["border gateway protocol", "routing"],
    "ospf":       ["routing protocol", "networking"],
    "mpls":       ["networking", "wan"],
    "tcp/ip":     ["networking", "network protocol"],
    "dns":        ["domain name system", "networking"],
    "dhcp":       ["network configuration", "ip management"],
    "vlan":       ["virtual lan", "network segmentation"],
    "firewall":   ["network security", "palo alto", "fortinet"],
    "load balancer":["nginx", "haproxy", "traffic management"],
    "cdn":        ["content delivery network", "cloudflare", "akamai"],

    # ── QA & Testing ──────────────────────────────────────────────
    "qa":         ["quality assurance", "testing", "software testing"],
    "qe":         ["quality engineering", "test automation", "qa"],
    "sdet":       ["software development engineer in test", "test automation", "qa"],
    "automation testing":["selenium", "playwright", "cypress", "test automation"],
    "selenium":   ["test automation", "web testing", "browser testing"],
    "playwright": ["test automation", "web testing", "browser testing"],
    "cypress":    ["test automation", "e2e testing", "javascript testing"],
    "appium":     ["mobile testing", "test automation"],
    "junit":      ["java testing", "unit testing"],
    "pytest":     ["python testing", "unit testing"],
    "jest":       ["javascript testing", "unit testing"],
    "mocha":      ["javascript testing", "unit testing"],
    "postman":    ["api testing", "rest testing"],
    "jmeter":     ["performance testing", "load testing"],
    "gatling":    ["performance testing", "load testing"],
    "locust":     ["load testing", "performance testing"],
    "sonarqube":  ["code quality", "static analysis"],
    "testng":     ["java testing", "selenium testing"],
    "cucumber":   ["bdd", "behavior driven development", "gherkin"],
    "bdd":        ["behavior driven development", "cucumber", "gherkin"],
    "tdd":        ["test driven development", "unit testing"],

    # ── Project Management & Agile ─────────────────────────────────
    "pm":         ["project manager", "product manager", "program manager"],
    "po":         ["product owner", "agile", "scrum"],
    "scrum":      ["agile", "sprints", "scrum master"],
    "kanban":     ["agile", "lean", "project management"],
    "agile":      ["scrum", "kanban", "sprint", "lean"],
    "pmp":        ["project management professional", "project manager"],
    "prince2":    ["project management", "project methodology"],
    "safe":       ["scaled agile", "enterprise agile"],
    "jira":       ["project management", "issue tracking", "atlassian"],
    "confluence":  ["documentation", "wiki", "atlassian"],
    "asana":      ["project management", "task management"],
    "trello":     ["project management", "kanban tool"],
    "notion":     ["documentation", "project management", "wiki"],
    "clickup":    ["project management", "task management"],
    "monday":     ["monday.com", "project management"],
    "basecamp":   ["project management", "team collaboration"],

    # ── Design & Creative ──────────────────────────────────────────
    "ui/ux":      ["user interface", "user experience", "product design"],
    "ux design":  ["user experience", "figma", "product design"],
    "ui design":  ["user interface", "figma", "graphic design"],
    "graphic design":["adobe", "illustrator", "photoshop", "visual design"],
    "photoshop":  ["adobe photoshop", "photo editing", "graphic design"],
    "illustrator":["adobe illustrator", "vector design", "graphic design"],
    "indesign":   ["adobe indesign", "layout design", "print design"],
    "after effects":["motion graphics", "video editing", "adobe"],
    "premiere":   ["adobe premiere", "video editing", "film"],
    "blender":    ["3d modeling", "3d animation", "vfx"],
    "maya":       ["autodesk maya", "3d modeling", "animation"],
    "3ds max":    ["autodesk 3ds", "3d modeling"],
    "cinema4d":   ["3d modeling", "motion graphics"],
    "unreal":     ["unreal engine", "game development", "3d"],
    "unity":      ["unity3d", "game development", "c#"],
    "motion graphics":["after effects", "animation", "visual effects"],
    "vfx":        ["visual effects", "cgi", "motion graphics"],
    "3d modeling":["blender", "maya", "3ds max", "cad"],
    "cad":        ["autocad", "solidworks", "3d design"],
    "autocad":    ["cad", "engineering design", "drafting"],
    "solidworks": ["cad", "mechanical design", "3d modeling"],
    "revit":      ["bim", "architectural design", "autodesk"],
    "bim":        ["building information modeling", "revit", "architecture"],

    # ── Business, Finance & Analytics ─────────────────────────────
    "ba":         ["business analyst", "business analysis", "requirements"],
    "brd":        ["business requirements document", "business analysis"],
    "frd":        ["functional requirements", "business analysis"],
    "crm":        ["customer relationship management", "salesforce", "hubspot"],
    "erp":        ["enterprise resource planning", "sap", "oracle erp", "oracle"],
    "sap":        ["erp", "enterprise software", "sap hana"],
    "salesforce": ["crm", "sfdc", "sales cloud"],
    "sfdc":       ["salesforce", "crm"],
    "hubspot":    ["crm", "marketing automation"],
    "zoho":       ["crm", "erp", "zoho crm"],
    "finance":    ["accounting", "financial analysis", "cfo"],
    "accounting": ["finance", "bookkeeping", "cpa"],
    "cpa":        ["certified public accountant", "accounting"],
    "ca":         ["chartered accountant", "accounting", "finance"],
    "cfa":        ["chartered financial analyst", "finance", "investment"],
    "frm":        ["financial risk manager", "risk management"],
    "fpa":        ["financial planning analysis", "finance", "forecasting"],
    "p&l":        ["profit and loss", "financial management"],
    "kpi":        ["key performance indicator", "metrics", "analytics"],
    "roi":        ["return on investment", "financial metrics"],
    "m&a":        ["mergers and acquisitions", "corporate finance"],
    "ipo":        ["initial public offering", "equity", "finance"],
    "vc":         ["venture capital", "investment", "startup funding"],
    "pe":         ["private equity", "investment", "buyout"],
    "excel":      ["microsoft excel", "spreadsheet", "data analysis"],
    "vba":        ["excel vba", "macro", "office automation"],
    "power query":["excel power query", "data transformation", "etl"],

    # ── Marketing & Growth ─────────────────────────────────────────
    "seo":        ["search engine optimization", "organic search", "digital marketing"],
    "sem":        ["search engine marketing", "ppc", "paid search", "google ads"],
    "ppc":        ["pay per click", "google ads", "paid advertising", "sem"],
    "cro":        ["conversion rate optimization", "a/b testing", "growth", "clinical research organization", "clinical trials"],
    "performance marketing":["ppc", "sem", "paid media", "growth marketing"],
    "growth hacking":["growth marketing", "user acquisition", "viral growth"],
    "content marketing":["blog", "copywriting", "inbound marketing"],
    "email marketing":["mailchimp", "klaviyo", "campaign management"],
    "social media marketing":["smm", "instagram", "facebook ads", "linkedin ads"],
    "smm":        ["social media marketing", "community management"],
    "affiliate marketing":["performance marketing", "partnerships"],
    "influencer marketing":["social media", "creator economy"],
    "brand management":["branding", "marketing strategy", "brand strategy"],
    "pr":         ["public relations", "communications", "media relations"],
    "gtm":        ["go to market", "product launch", "marketing strategy"],

    # ── HR & People ───────────────────────────────────────────────
    "hr":         ["human resources", "people operations", "talent"],
    "hrbp":       ["hr business partner", "human resources", "people"],
    "ta":         ["talent acquisition", "recruiting", "hr"],
    "l&d":        ["learning and development", "training", "hr"],
    "hris":       ["hr information system", "hr software", "workday"],
    "workday":    ["hris", "hr software", "payroll"],
    "payroll":    ["compensation", "hr", "salary processing"],
    "comp":       ["compensation", "total rewards", "benefits"],
    "dei":        ["diversity equity inclusion", "hr", "culture"],
    "oha":        ["organizational health", "culture", "hr"],

    # ── Sales ─────────────────────────────────────────────────────
    "sdr":        ["sales development representative", "inside sales", "bdr"],
    "bdr":        ["business development representative", "sdr", "sales"],
    "ae":         ["account executive", "sales", "closing"],
    "am":         ["account manager", "client success", "sales"],
    "csm":        ["customer success manager", "account management"],
    "bd":         ["business development", "partnerships", "sales"],
    "b2b":        ["business to business", "enterprise sales"],
    "b2c":        ["business to consumer", "consumer sales"],
    "smb":        ["small medium business", "mid-market sales"],
    "enterprise sales":["b2b", "large account", "strategic sales"],
    "saas sales": ["software sales", "b2b", "subscription sales"],

    # ── Operations & Supply Chain ─────────────────────────────────
    "ops":        ["operations", "business operations"],
    "scm":        ["supply chain management", "logistics", "procurement"],
    "wms":        ["warehouse management system", "logistics"],
    "tms":        ["transport management system", "logistics"],
    "lean":       ["lean manufacturing", "six sigma", "process improvement"],
    "six sigma":  ["lean", "process improvement", "quality management"],
    "kaizen":     ["continuous improvement", "lean", "operations"],
    "iso":        ["iso certification", "quality management", "compliance"],

    # ── Engineering & Manufacturing ────────────────────────────────
    "mechanical engineering":["mech", "cad", "product design"],
    "civil engineering":     ["structural", "construction", "infrastructure"],
    "electrical engineering":["ee", "electronics", "power systems"],
    "ee":                    ["electrical engineering", "electronics"],
    "ece":                   ["electronics communication", "embedded", "vlsi"],
    "vlsi":                  ["chip design", "fpga", "semiconductor"],
    "fpga":                  ["field programmable gate array", "vlsi", "embedded"],
    "embedded systems":      ["firmware", "rtos", "iot", "c programming"],
    "firmware":              ["embedded", "rtos", "microcontroller"],
    "rtos":                  ["real time os", "embedded", "firmware"],
    "iot":                   ["internet of things", "embedded", "mqtt"],
    "plc":                   ["programmable logic controller", "automation", "scada"],
    "scada":                 ["industrial control", "plc", "automation"],
    "robotics":              ["ros", "automation", "mechatronics"],
    "ros":                   ["robot operating system", "robotics"],
    "cfd":                   ["computational fluid dynamics", "simulation"],
    "fea":                   ["finite element analysis", "simulation", "ansys"],
    "ansys":                 ["fea", "simulation", "engineering software"],

    # ── Healthcare & Life Sciences ─────────────────────────────────
    "pharma":     ["pharmaceutical", "drug development", "life sciences"],
    "clinical":   ["clinical trials", "healthcare", "medical research"],
    "regulatory": ["regulatory affairs", "fda", "compliance", "pharma"],
    "bioinformatics":["computational biology", "genomics", "life sciences"],
    "biotech":    ["biotechnology", "life sciences", "biology"],
    "medtech":    ["medical technology", "medical devices", "healthcare"],
    "ehr":        ["electronic health record", "healthcare it", "emr"],
    "emr":        ["electronic medical record", "ehr", "healthcare it"],
    "hl7":        ["healthcare interoperability", "fhir", "health data"],
    "fhir":       ["healthcare data standard", "hl7", "interoperability"],

    # ── Certifications ────────────────────────────────────────────
    "aws certified":    ["aws certification", "cloud certification"],
    "gcp certified":    ["google cloud certification"],
    "azure certified":  ["microsoft certification", "az-900"],
    "cka":              ["certified kubernetes administrator", "kubernetes"],
    "ckad":             ["certified kubernetes developer", "kubernetes"],
    "rhce":             ["red hat certified", "linux certification"],
    "rhcsa":            ["red hat certified", "linux"],
    "cissp":            ["security certification", "information security"],
    "ceh":              ["certified ethical hacker", "pentesting"],
    "oscp":             ["offensive security", "pentesting certification"],
    "pmp":              ["project management professional", "certification"],
    "itil":             ["it service management", "itsm", "service desk"],
    "togaf":            ["enterprise architecture", "architecture framework"],
    "scrum master":     ["csm", "agile", "scrum certification"],
    "csm":              ["certified scrum master", "agile", "scrum"],
    "safe agilist":     ["scaled agile", "safe certification"],

    # ── Roles & Seniority ─────────────────────────────────────────
    "sde":        ["software development engineer", "software engineer", "developer"],
    "swe":        ["software engineer", "sde", "developer"],
    "sde1":       ["junior software engineer", "entry level developer"],
    "sde2":       ["software engineer", "mid level developer"],
    "sde3":       ["senior software engineer", "staff engineer"],
    "senior":     ["sr", "senior engineer", "lead"],
    "sr":         ["senior"],
    "junior":     ["jr", "entry level", "associate"],
    "jr":         ["junior", "entry level"],
    "lead":       ["tech lead", "team lead", "principal"],
    "staff":      ["staff engineer", "principal", "senior staff"],
    "principal":  ["principal engineer", "staff", "architect"],
    "architect":  ["solution architect", "enterprise architect", "technical architect"],
    "cto":        ["chief technology officer", "tech leadership"],
    "coo":        ["chief operating officer", "operations leadership"],
    "cfo":        ["chief financial officer", "finance leadership"],
    "cpo":        ["chief product officer", "product leadership"],
    "ciso":       ["chief information security officer", "security leadership"],
    "vp":         ["vice president", "vp engineering", "vp product"],
    "director":   ["director of engineering", "engineering director"],
    "manager":    ["engineering manager", "team manager", "dev manager"],
    "intern":     ["internship", "trainee", "fresher"],
    "fresher":    ["entry level", "intern", "graduate"],
    "trainee":    ["intern", "fresher", "junior"],
},
        "displayedAttributes": ["*"],
        "pagination": {"maxTotalHits": 50000},
    },
}


# Share the full synonym dict across all three indexes — single source of truth
_SYNONYMS = INDEX_CONFIGS["companies"]["synonyms"]
INDEX_CONFIGS["jobs"]["synonyms"]  = _SYNONYMS
INDEX_CONFIGS["users"]["synonyms"] = _SYNONYMS


def _req(method: str, path: str, **kwargs) -> requests.Response:
    return requests.request(method, f"{MEILI_URL}{path}", headers=HEADERS, timeout=30, **kwargs)


def create_index(uid: str, primary_key: str = "id") -> Optional[int]:
    r = _req("POST", "/indexes", json={"uid": uid, "primaryKey": primary_key})
    if r.status_code == 409:
        print(f"  [skip]  Index '{uid}' already exists — skipping creation.")
        return None
    if r.status_code not in (200, 201, 202):
        raise RuntimeError(f"Create index '{uid}' failed: {r.status_code} {r.text}")
    task_uid = r.json().get("taskUid")
    print(f"  [ok]    Index '{uid}' creation enqueued (task: {task_uid})")
    return task_uid


def apply_settings(uid: str, config: Dict[str, Any]) -> List[int]:
    SETTINGS_KEYS = {
        "searchableAttributes",
        "filterableAttributes",
        "sortableAttributes",
        "rankingRules",
        "typoTolerance",
        "proximityPrecision",
        "nonSeparatorTokens",
        "separatorTokens",
        "stopWords",
        "synonyms",
        "displayedAttributes",
        "pagination",
    }
    payload = {k: v for k, v in config.items() if k in SETTINGS_KEYS}
    r = _req("PATCH", f"/indexes/{uid}/settings", json=payload)
    if r.status_code not in (200, 202):
        raise RuntimeError(f"Settings update for '{uid}' failed: {r.status_code} {r.text}")
    task_uid = r.json().get("taskUid")
    print(f"  [ok]    Settings for '{uid}' enqueued (task: {task_uid})")
    return [task_uid]


def wait_for_tasks(task_uids: List[int], poll_interval: float = 1.0) -> None:
    pending = set(task_uids)
    print(f"\nWaiting for {len(pending)} task(s): {sorted(pending)}")
    while pending:
        done = set()
        for uid in list(pending):
            r = _req("GET", f"/tasks/{uid}")
            if r.status_code == 200:
                status = r.json().get("status", "")
                if status in ("succeeded", "failed", "canceled"):
                    result = r.json()
                    if status == "succeeded":
                        print(f"  [done]  Task {uid} succeeded.")
                    else:
                        print(f"  [FAIL]  Task {uid} {status}: {result.get('error')}")
                    done.add(uid)
        pending -= done
        if pending:
            time.sleep(poll_interval)
    print("All tasks complete.")


def setup(indexes: List[str], wait: bool) -> None:
    all_task_uids: List[int] = []
    for idx in indexes:
        config = INDEX_CONFIGS[idx]
        print(f"\n── {idx} ──────────────────────────────────")
        pk = config.get("primaryKey", "id")
        t = create_index(idx, pk)
        if t:
            all_task_uids.append(t)
        task_uids = apply_settings(idx, config)
        all_task_uids.extend(task_uids)

    if wait and all_task_uids:
        wait_for_tasks(all_task_uids)
    else:
        print(f"\nDone. {len(all_task_uids)} task(s) enqueued. Pass --wait to block until finished.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure Meilisearch indexes.")
    parser.add_argument("--index", choices=list(INDEX_CONFIGS.keys()), help="Only configure this index (default: all)")
    parser.add_argument("--wait", action="store_true", default=False, help="Wait for Meilisearch tasks to complete")
    args = parser.parse_args()

    indexes = [args.index] if args.index else list(INDEX_CONFIGS.keys())
    setup(indexes, wait=args.wait)


if __name__ == "__main__":
    main()
