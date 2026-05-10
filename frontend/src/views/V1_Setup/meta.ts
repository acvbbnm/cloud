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
  'iam-takeover': {
    id: 'iam-takeover',
    label: 'IAM 계정 탈취',
    icon: '🔑',
    severity: 'CRITICAL',
    sevColor: '#FF4444',
    desc: 'IAM 권한 탈취 → 시스템 변조 · 악성 리소스 생성',
    hint:
      'T1078→T1098 패턴: 비인가 로그인 후 IAM 권한 상승 흐름을 추적하세요. 신규 생성 계정과 API Key 발급 이력을 즉시 확인하세요.',
    services: {
      naver: ['Cloud Activity Tracer', 'Sub Account', 'OS Security Checker'],
      nhn: ['CloudTrail', 'IAM 멤버 현황', 'Security Monitoring'],
      all: ['NCP Activity Tracer', 'NHN CloudTrail', '양쪽 IAM 변경 이력'],
    },
    mitre: ['T1078', 'T1098', 'T1136'],
    techniqueShort: 'T1078, T1098, T1530',
  },
  insider: {
    id: 'insider',
    label: '내부자 위협',
    icon: '👤',
    severity: 'HIGH',
    sevColor: '#FFB020',
    desc: '내부 사용자에 의한 비인가 데이터 접근 / 유출',
    hint:
      '평소 접근 패턴 대비 이상 다운로드량·심야 접근·미사용 권한 사용 여부를 추적하세요. 퇴직자·인사 이동 직원의 자격증명 활성 여부를 확인하세요.',
    services: {
      naver: ['Activity Tracer', 'Object Storage 액세스 로그', 'Sub Account'],
      nhn: ['CloudTrail', 'Object Storage 접근 로그', 'IAM'],
      all: ['양쪽 Activity Tracer/CloudTrail', '양쪽 Object Storage 접근 로그'],
    },
    mitre: ['T1537', 'T1567', 'T1530'],
    techniqueShort: 'T1537, T1567',
  },
  credential: {
    id: 'credential',
    label: '자격증명 유출',
    icon: '🔓',
    severity: 'CRITICAL',
    sevColor: '#FF4444',
    desc: 'API 키 · Access Key · OAuth 토큰 노출 → 무단 사용',
    hint:
      '코드 저장소·환경 변수·Public 버킷 어디에 자격증명이 노출됐는지 즉시 검색하세요. 노출 키의 최근 사용 이력과 발급 이벤트를 함께 확인하세요.',
    services: {
      naver: ['Activity Tracer', 'API Usage Statistics', 'Sub Account'],
      nhn: ['CloudTrail', 'API Gateway 통계', 'Secure Key Manager'],
      all: ['양쪽 API Key/Access Key 사용 이력', '양쪽 Activity Tracer/CloudTrail'],
    },
    mitre: ['T1552', 'T1078', 'T1098'],
    techniqueShort: 'T1552, T1078',
  },
  webapp: {
    id: 'webapp',
    label: '웹 애플리케이션 공격',
    icon: '🌐',
    severity: 'HIGH',
    sevColor: '#FFB020',
    desc: 'SQLi · RCE · Path Traversal 등 웹 취약점 악용',
    hint:
      '웹 접근 로그에서 공격 패턴을 검색하고 권한 상승 흔적을 확인하세요. WAF 차단 이벤트와 비정상 응답 코드 비율을 함께 보세요.',
    services: {
      naver: ['Cloud Log Analytics', 'System Security Checker', 'Activity Tracer'],
      nhn: ['Log & Crash Search', 'Security Monitoring', 'CloudTrail'],
      all: ['양쪽 Log Analytics/Crash Search', '양쪽 Security Checker/Monitoring'],
    },
    mitre: ['T1190', 'T1059', 'T1505.003'],
    techniqueShort: 'T1190, T1059',
  },
  ransomware: {
    id: 'ransomware',
    label: '랜섬웨어',
    icon: '💀',
    severity: 'CRITICAL',
    sevColor: '#FF4444',
    desc: '클라우드 리소스 암호화 / 스냅샷 삭제 → 금전 요구',
    hint:
      'Object Storage 객체 대량 변경·삭제 이벤트와 스냅샷 / 백업 무단 삭제를 즉시 확인하세요. 권한 상승 후 Storage Encryption 설정 변경 이벤트가 핵심 단서입니다.',
    services: {
      naver: ['Object Storage', 'Activity Tracer', 'Cloud Insight'],
      nhn: ['Object Storage', 'CloudTrail', 'Cloud Monitoring'],
      all: ['양쪽 Object Storage', '양쪽 Activity Tracer/CloudTrail'],
    },
    mitre: ['T1486', 'T1490', 'T1485'],
    techniqueShort: 'T1486, T1490',
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
