export interface CspMeta {
  id: string;
  label: string;
  short: string;
  color: string;
  desc: string;
  services: string[];
  security: string[];
}

export const CSP_META: Record<string, CspMeta> = {
  naver: {
    id: 'naver',
    label: 'Naver Cloud Platform',
    short: 'NCP',
    color: '#1A6BFF',
    desc: 'Activity Tracer · Sub Account · Object Storage',
    services: [
      'Activity Tracer',
      'Cloud Log Analytics',
      'Sub Account',
      'Object Storage',
      'VPC Flow Log',
      'Cloud Insight',
      'System Security Checker',
      'API Gateway',
    ],
    security: [
      'Webshell Behavior Detector',
      'Threat Detection',
      'WAF',
      'Anti-DDoS',
      'VPC Flow Log',
    ],
  },
  nhn: {
    id: 'nhn',
    label: 'NHN Cloud',
    short: 'NHN',
    color: '#00D4AA',
    desc: 'CloudTrail · IAM · Object Storage',
    services: [
      'CloudTrail',
      'Log & Crash Search',
      'IAM',
      'Object Storage',
      'VPC Flow Log',
      'Cloud Monitoring',
      'Security Monitoring',
      'API Gateway',
    ],
    security: [
      'Security Monitoring',
      'WAF',
      'Anti-DDoS',
      'Network Security (IDS/IPS)',
      'Log & Crash Search',
    ],
  },
  all: {
    id: 'all',
    label: '멀티 CSP (NCP + NHN)',
    short: '멀티',
    color: '#8B5CF6',
    desc: '양쪽 Activity Tracer/CloudTrail · 양쪽 IAM/Storage',
    services: [
      'NCP Activity Tracer',
      'NHN CloudTrail',
      '양쪽 IAM/Sub Account',
      '양쪽 Object Storage',
      '크로스 CSP VPC Flow Log',
    ],
    security: ['NCP Threat Detection', 'NHN Security Monitoring', 'SIEM 통합'],
  },
};

export interface IncidentTypeMeta {
  id: string;
  label: string;
  icon: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  sevColor: string;
  desc: string;
  hint: string;
  services: { naver: string[]; nhn: string[]; all: string[] };
  mitre: string[];
  techniqueShort: string;
}

export const TYPE_META: Record<string, IncidentTypeMeta> = {
  CREDENTIAL_THEFT: {
    id: 'CREDENTIAL_THEFT',
    label: '자격증명 탈취',
    icon: '',
    severity: 'CRITICAL',
    sevColor: '#FF4444',
    desc: '콘솔 비밀번호·Access Key·API 키 탈취 → 비인가 로그인·SubAccount 생성',
    hint:
      'T1078.004 → T1098.001 패턴: 비국내 IP·비업무시간 로그인, 신규 SubAccount 생성, AccessKey 발급, Decrypt root password 이벤트를 즉시 확인하세요.',
    services: {
      naver: ['Activity Tracer', 'Sub Account', 'Server Console'],
      nhn: ['Cloud Trail', 'IAM', 'S3 Credential'],
      all: ['NCP Activity Tracer', 'NHN Cloud Trail', '양쪽 IAM 변경 이력'],
    },
    mitre: ['T1078.004', 'T1098.001', 'T1552'],
    techniqueShort: 'T1078, T1098, T1552',
  },
  PRIVILEGE_ESCALATION: {
    id: 'PRIVILEGE_ESCALATION',
    label: '권한 상승',
    icon: '',
    severity: 'CRITICAL',
    sevColor: '#FF4444',
    desc: '일반 계정 → 관리자 권한 / 정책 부여 / 멤버 역할 변경 — 권한 확대',
    hint:
      'Attach/Replace policy to sub account, project.product.enable, member.role.update 이벤트와 신규 정책의 부여 대상을 추적하세요. 짧은 시간 내 다수 권한 변경이 핵심 단서입니다.',
    services: {
      naver: ['Activity Tracer', 'Sub Account 정책 변경', 'Resource Manager'],
      nhn: ['Cloud Trail', 'IAM Role Group', 'Project Member'],
      all: ['양쪽 IAM/Sub Account 변경 이력', '양쪽 권한 부여 이벤트'],
    },
    mitre: ['T1098', 'T1078.004'],
    techniqueShort: 'T1098',
  },
  DATA_EXFILTRATION: {
    id: 'DATA_EXFILTRATION',
    label: '데이터 유출',
    icon: '',
    severity: 'HIGH',
    sevColor: '#FFB020',
    desc: 'Object Storage 대용량 다운로드 · 외부 전송 — 기밀 데이터 반출',
    hint:
      'Export To Object Storage, object.upload, GetObject 대량 이벤트와 출처 IP를 추적하세요. 정책 변경 직후 발생한 접근을 우선 확인하세요.',
    services: {
      naver: ['Activity Tracer', 'Object Storage 접근 로그', 'Cloud Log Analytics'],
      nhn: ['Cloud Trail', 'Object Storage 접근 로그'],
      all: ['양쪽 Object Storage', '양쪽 Activity Tracer/Cloud Trail'],
    },
    mitre: ['T1537', 'T1567'],
    techniqueShort: 'T1537, T1567',
  },
  AUDIT_LOG_TAMPERING: {
    id: 'AUDIT_LOG_TAMPERING',
    label: '감사 로그 변조',
    icon: '',
    severity: 'CRITICAL',
    sevColor: '#FF4444',
    desc: '활동 추적·감사 로그 비활성화 / 삭제 — 침해 흔적 제거',
    hint:
      'Delete Tracer, Disable/Remove AccessKey, s3credential.delete, 로그 보존 설정 변경 이벤트를 즉시 확인하세요. 평소 대비 누락된 로그 구간(시간 갭)이 강한 신호입니다.',
    services: {
      naver: ['Activity Tracer 설정', 'Sub Account AccessKey 변경'],
      nhn: ['Cloud Trail 설정', 'IAM 자격증명 변경'],
      all: ['양쪽 감사 추적 설정 변경 이력', '양쪽 자격증명 폐기 이력'],
    },
    mitre: ['T1562.008', 'T1070', 'T1531'],
    techniqueShort: 'T1562, T1070',
  },
  MULTI_CSP_LATERAL: {
    id: 'MULTI_CSP_LATERAL',
    label: '멀티 CSP 횡적 이동',
    icon: '',
    severity: 'CRITICAL',
    sevColor: '#FF4444',
    desc: '한 CSP의 자격증명·IP가 다른 CSP에서도 활동 — 크로스 CSP 침투',
    hint:
      '같은 외부 IP가 NCP/NHN 양쪽에서 활동한 시점, 동일 사용자명·이메일이 양쪽에 존재하는지 cross-CSP 상관관계 분석. 단일 CSP 모니터링으로는 보이지 않습니다.',
    services: {
      naver: ['Activity Tracer (sourceIp)', 'Sub Account', 'Access Server Console'],
      nhn: ['Cloud Trail (userIp)', 'IAM', 'Instance Action'],
      all: ['양쪽 src_endpoint.ip 교차 조회', 'OCSF 정규화 후 cross-CSP 분석'],
    },
    mitre: ['T1021', 'T1078.004'],
    techniqueShort: 'T1021, T1078',
  },
};

export interface CollectionItem {
  name: string;
  priority: 1 | 2 | 3 | 4;
  layer: 'cloud' | 'server' | 'network' | 'app';
  hint: string;
  cmd?: string;
  path?: string;
  retention: string;
  auto: boolean;
  mitre: string[];
}

export interface CollectionGuide {
  ctx: string;
  required: CollectionItem[];
  corroborating: CollectionItem[];
}

const baseGuide = (csp: 'naver' | 'nhn' | 'all'): CollectionGuide => {
  const isNhn = csp === 'nhn';
  const isAll = csp === 'all';
  const tracer = isNhn ? 'CloudTrail' : 'Activity Tracer';
  const storage = isNhn ? '컨테이너' : '버킷';
  return {
    ctx: '비인가 로그인 → IAM 권한 상승 → Object Storage 무단 다운로드 흐름을 우선 추적하세요. 90일 보존 한계가 있는 클라우드 이벤트와 휘발성 서버 세션 정보부터 즉시 확보합니다.',
    required: [
      {
        name: '실행 중인 프로세스 / 네트워크 세션',
        priority: 1,
        layer: 'server',
        hint: '서버 라이브 상태에서만 수집 가능. 공격자 프로세스·리버스 셸 즉시 확인',
        cmd: 'ps auxwf > /tmp/ps.txt && ss -tunap > /tmp/ss.txt',
        retention: '휘발성 — 재부팅 시 소멸',
        auto: false,
        mitre: ['T1078', 'T1059'],
      },
      {
        name: `콘솔 로그인 이벤트 (${tracer})`,
        priority: 3,
        layer: 'cloud',
        hint: `${tracer} → 로그인 이벤트 → 해외 IP·새벽 시간대 필터링`,
        cmd: isNhn
          ? 'curl -H "Authorization: Bearer $TOKEN" "https://audit.api.nhncloudservice.com/v1.0/appkeys/$APPKEY/audit-logs" > audit.json'
          : 'ncloud activity-tracer search --output json > activity.json',
        retention: '90일',
        auto: true,
        mitre: ['T1078'],
      },
      {
        name: `${isAll ? '양쪽 ' : ''}IAM / Sub Account 변경 이력`,
        priority: 3,
        layer: 'cloud',
        hint: 'addSubAccountRole / attachPolicy / Member 역할 변경 이벤트 필터',
        retention: '90일',
        auto: true,
        mitre: ['T1098', 'T1136'],
      },
      {
        name: `Object Storage ${storage} 정책 변경 이벤트`,
        priority: 3,
        layer: 'cloud',
        hint: `putBucketPolicy 등 ${storage} 정책 변경 → 비정상 시각·미인가 계정 변경 확인`,
        retention: '90일',
        auto: true,
        mitre: ['T1530'],
      },
      {
        name: 'Object Storage GetObject 대량 이벤트',
        priority: 3,
        layer: 'cloud',
        hint: '단시간 대용량 다운로드 — 데이터 유출 지표',
        retention: '설정 시 무제한',
        auto: true,
        mitre: ['T1537'],
      },
    ],
    corroborating: [
      {
        name: '서버 OS 인증 로그',
        priority: 2,
        layer: 'server',
        hint: 'SSH 로그인 시도·성공 이력. 로그 로테이션 전 즉시 수집',
        cmd: 'cp /var/log/auth.log* /mnt/evidence/',
        path: '/var/log/auth.log',
        retention: '로테이션 (보통 4주)',
        auto: false,
        mitre: ['T1078', 'T1110'],
      },
      {
        name: 'VPC Flow Log',
        priority: 3,
        layer: 'network',
        hint: '비정상 인바운드/아웃바운드 트래픽 확인',
        retention: '기본 30일',
        auto: true,
        mitre: ['T1071'],
      },
      {
        name: 'MFA 설정 / Key Pair 현황',
        priority: 4,
        layer: 'cloud',
        hint: 'ADMIN 계정 MFA 미설정·신규 등록 Key Pair 전수 확인',
        retention: '정적',
        auto: false,
        mitre: ['T1556', 'T1098'],
      },
    ],
  };
};

export const buildGuide = (
  type: string,
  csp: 'naver' | 'nhn' | 'all',
): CollectionGuide => {
  // 동일한 5종에 대해 CSP만 토큰 치환한 기본 가이드를 반환합니다.
  // 백엔드 KB 연동 후 type별 차별화는 서버 측에서 수행합니다.
  void type;
  return baseGuide(csp);
};
