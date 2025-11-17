--
-- PostgreSQL database dump
--

\restrict 7NEpKoMjZazrG89Qagap8Uaj8QxacQHLaigIHr6qJ4N6ZabDuSiPq19Ljg7HCm9

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.6 (Ubuntu 17.6-2.pgdg22.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admin_users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admin_users (
    id integer NOT NULL,
    username character varying(100) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(50) DEFAULT 'user'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_login timestamp without time zone,
    is_active boolean DEFAULT true
);


ALTER TABLE public.admin_users OWNER TO postgres;

--
-- Name: TABLE admin_users; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.admin_users IS 'Admin dashboard users with role-based access';


--
-- Name: admin_users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.admin_users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.admin_users_id_seq OWNER TO postgres;

--
-- Name: admin_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.admin_users_id_seq OWNED BY public.admin_users.id;


--
-- Name: anonymization_jobs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.anonymization_jobs (
    id integer NOT NULL,
    job_id character varying(100) NOT NULL,
    k_value integer NOT NULL,
    time_window integer NOT NULL,
    start_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    end_time timestamp without time zone,
    status character varying(50) DEFAULT 'pending'::character varying,
    records_processed integer,
    error_message text
);


ALTER TABLE public.anonymization_jobs OWNER TO postgres;

--
-- Name: TABLE anonymization_jobs; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.anonymization_jobs IS 'Central anonymization batch job tracking';


--
-- Name: anonymization_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.anonymization_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.anonymization_jobs_id_seq OWNER TO postgres;

--
-- Name: anonymization_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.anonymization_jobs_id_seq OWNED BY public.anonymization_jobs.id;


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.audit_logs (
    id integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    user_id character varying(100) NOT NULL,
    action character varying(255) NOT NULL,
    ip_address character varying(45),
    details jsonb,
    success boolean DEFAULT true
);


ALTER TABLE public.audit_logs OWNER TO postgres;

--
-- Name: TABLE audit_logs; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.audit_logs IS 'Audit trail of all admin actions';


--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_logs_id_seq OWNER TO postgres;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: fl_rounds; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fl_rounds (
    id integer NOT NULL,
    round_number integer NOT NULL,
    start_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    end_time timestamp without time zone,
    status character varying(50) DEFAULT 'pending'::character varying,
    clients_participated integer DEFAULT 0,
    global_model_accuracy double precision,
    notes text
);


ALTER TABLE public.fl_rounds OWNER TO postgres;

--
-- Name: TABLE fl_rounds; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.fl_rounds IS 'Federated learning training round history';


--
-- Name: fl_rounds_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.fl_rounds_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.fl_rounds_id_seq OWNER TO postgres;

--
-- Name: fl_rounds_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.fl_rounds_id_seq OWNED BY public.fl_rounds.id;


--
-- Name: privacy_policies; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.privacy_policies (
    id integer NOT NULL,
    unique_key character varying(512) NOT NULL,
    k_value integer DEFAULT 5 NOT NULL,
    time_window integer DEFAULT 5 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(100),
    is_remote boolean DEFAULT false
);


ALTER TABLE public.privacy_policies OWNER TO postgres;

--
-- Name: TABLE privacy_policies; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.privacy_policies IS 'Privacy policy configurations per patient';


--
-- Name: privacy_policies_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.privacy_policies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.privacy_policies_id_seq OWNER TO postgres;

--
-- Name: privacy_policies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.privacy_policies_id_seq OWNED BY public.privacy_policies.id;


--
-- Name: sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sessions (
    id integer NOT NULL,
    unique_key character varying(512) NOT NULL,
    session_id character varying(255),
    session_start timestamp without time zone NOT NULL,
    session_end timestamp without time zone,
    duration_seconds integer,
    data_points_collected integer,
    anonymization_applied boolean DEFAULT false,
    k_value integer,
    time_window integer
);


ALTER TABLE public.sessions OWNER TO postgres;

--
-- Name: TABLE sessions; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.sessions IS 'Patient session tracking for analytics';


--
-- Name: sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sessions_id_seq OWNER TO postgres;

--
-- Name: sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sessions_id_seq OWNED BY public.sessions.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    unique_key character varying(512) NOT NULL,
    device_id character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_session timestamp without time zone,
    privacy_settings jsonb,
    status character varying(50) DEFAULT 'active'::character varying,
    notes text
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: TABLE users; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.users IS 'Patient metadata linked by SHA256-hashed unique_key';


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: admin_users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_users ALTER COLUMN id SET DEFAULT nextval('public.admin_users_id_seq'::regclass);


--
-- Name: anonymization_jobs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.anonymization_jobs ALTER COLUMN id SET DEFAULT nextval('public.anonymization_jobs_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: fl_rounds id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fl_rounds ALTER COLUMN id SET DEFAULT nextval('public.fl_rounds_id_seq'::regclass);


--
-- Name: privacy_policies id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.privacy_policies ALTER COLUMN id SET DEFAULT nextval('public.privacy_policies_id_seq'::regclass);


--
-- Name: sessions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions ALTER COLUMN id SET DEFAULT nextval('public.sessions_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: admin_users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.admin_users (id, username, password_hash, role, created_at, last_login, is_active) FROM stdin;
1	admin	240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9	admin	2025-11-06 14:36:39.151748	\N	t
\.


--
-- Data for Name: anonymization_jobs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.anonymization_jobs (id, job_id, k_value, time_window, start_time, end_time, status, records_processed, error_message) FROM stdin;
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.audit_logs (id, "timestamp", user_id, action, ip_address, details, success) FROM stdin;
\.


--
-- Data for Name: fl_rounds; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.fl_rounds (id, round_number, start_time, end_time, status, clients_participated, global_model_accuracy, notes) FROM stdin;
\.


--
-- Data for Name: privacy_policies; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.privacy_policies (id, unique_key, k_value, time_window, created_at, updated_at, created_by, is_remote) FROM stdin;
1	575e50b792ce26d6b7e7b155fbd7e502a96091b659ba226d7c17a96481561935	5	5	2025-11-06 14:36:39.218844	2025-11-06 14:36:39.218844	\N	f
2	0000004000000000000000000080000000010000000000000000000000000000	5	5	2025-11-13 13:04:49.954001	2025-11-13 13:04:49.954002	\N	t
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sessions (id, unique_key, session_id, session_start, session_end, duration_seconds, data_points_collected, anonymization_applied, k_value, time_window) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, unique_key, device_id, created_at, last_session, privacy_settings, status, notes) FROM stdin;
1	575e50b792ce26d6b7e7b155fbd7e502a96091b659ba226d7c17a96481561935	test_device_001	2025-11-06 14:36:39.214089	2025-11-06 14:36:39.214089	{"k_value": 5, "time_window": 5, "auto_anonymize": true}	active	\N
2	0000000000000000000008008000000000000000000000000000000100000000	6c:1d:eb:06:57:9c	2025-11-09 18:05:40.038288	2025-11-11 14:09:58.396988	{"k_value": 3, "time_window": 30, "auto_anonymize": true}	active	\N
15	0000004000000000000000000080000000010000000000000000000000000000	6C:1D:EB:06:57:9C	2025-11-13 11:42:30.287983	2025-11-13 13:05:15.180567	{"k_value": 5, "time_window": 5, "auto_anonymize": true}	active	\N
\.


--
-- Name: admin_users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.admin_users_id_seq', 1, true);


--
-- Name: anonymization_jobs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.anonymization_jobs_id_seq', 1, false);


--
-- Name: audit_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.audit_logs_id_seq', 1, false);


--
-- Name: fl_rounds_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.fl_rounds_id_seq', 1, false);


--
-- Name: privacy_policies_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.privacy_policies_id_seq', 2, true);


--
-- Name: sessions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sessions_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 19, true);


--
-- Name: admin_users admin_users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_pkey PRIMARY KEY (id);


--
-- Name: admin_users admin_users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_username_key UNIQUE (username);


--
-- Name: anonymization_jobs anonymization_jobs_job_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.anonymization_jobs
    ADD CONSTRAINT anonymization_jobs_job_id_key UNIQUE (job_id);


--
-- Name: anonymization_jobs anonymization_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.anonymization_jobs
    ADD CONSTRAINT anonymization_jobs_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: fl_rounds fl_rounds_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fl_rounds
    ADD CONSTRAINT fl_rounds_pkey PRIMARY KEY (id);


--
-- Name: privacy_policies privacy_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.privacy_policies
    ADD CONSTRAINT privacy_policies_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_unique_key_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_unique_key_key UNIQUE (unique_key);


--
-- Name: idx_anon_jobs_start; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_anon_jobs_start ON public.anonymization_jobs USING btree (start_time);


--
-- Name: idx_anon_jobs_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_anon_jobs_status ON public.anonymization_jobs USING btree (status);


--
-- Name: idx_audit_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_timestamp ON public.audit_logs USING btree ("timestamp");


--
-- Name: idx_audit_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_user ON public.audit_logs USING btree (user_id);


--
-- Name: idx_fl_rounds_start; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fl_rounds_start ON public.fl_rounds USING btree (start_time);


--
-- Name: idx_fl_rounds_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fl_rounds_status ON public.fl_rounds USING btree (status);


--
-- Name: idx_policies_unique_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_policies_unique_key ON public.privacy_policies USING btree (unique_key);


--
-- Name: idx_sessions_start; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sessions_start ON public.sessions USING btree (session_start);


--
-- Name: idx_sessions_unique_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sessions_unique_key ON public.sessions USING btree (unique_key);


--
-- Name: idx_users_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_created_at ON public.users USING btree (created_at);


--
-- Name: idx_users_last_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_last_session ON public.users USING btree (last_session);


--
-- Name: idx_users_unique_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_unique_key ON public.users USING btree (unique_key);


--
-- Name: privacy_policies privacy_policies_unique_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.privacy_policies
    ADD CONSTRAINT privacy_policies_unique_key_fkey FOREIGN KEY (unique_key) REFERENCES public.users(unique_key) ON DELETE CASCADE;


--
-- Name: sessions sessions_unique_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_unique_key_fkey FOREIGN KEY (unique_key) REFERENCES public.users(unique_key) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict 7NEpKoMjZazrG89Qagap8Uaj8QxacQHLaigIHr6qJ4N6ZabDuSiPq19Ljg7HCm9

