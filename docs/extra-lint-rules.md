# SAM CLI 추가 Lint 규칙 사용 가이드

AWS SAM CLI의 `validate` 명령어는 템플릿 검증을 위해 [cfn-lint](https://github.com/aws-cloudformation/cfn-lint)를 사용합니다. 
이제 SAM CLI는 `--extra-lint-rules` 옵션을 통해 추가 lint 규칙을 지원합니다.

## 사용 방법

```bash
sam validate --lint --extra-lint-rules="cfn_lint_serverless.rules"
```

## 인스톨러로 SAM CLI 설치 시 고려사항

SAM CLI를 인스톨러(설치 프로그램)로 설치한 경우, SAM CLI는 자체 Python 환경을 사용합니다. 이 경우 추가 규칙 모듈이 해당 환경에 설치되어 있어야 합니다. 이 때 두 가지 접근 방식이 있습니다:

1. **인스톨러 Python 환경에 패키지 설치**: 인스톨러의 Python 환경에 필요한 패키지를 설치합니다.
2. **모듈 경로를 전체 경로로 지정**: 사용자 환경에 설치된 패키지의 전체 경로를 지정합니다.

## 사용 예제

### 서버리스 규칙 사용 (cfn-lint-serverless)

```bash
# 먼저 패키지 설치
pip install cfn-lint-serverless

# SAM 템플릿 검증 실행
sam validate --lint --extra-lint-rules="cfn_lint_serverless.rules"
```

### 여러 규칙 모듈 사용

#### 방법 1: 콤마(,)로 구분하여 지정

여러 규칙 모듈을 콤마(,)로 구분하여 한 번의 옵션으로 지정할 수 있습니다:

```bash
sam validate --lint --extra-lint-rules="module1.rules,module2.rules,module3.rules"
```

각 모듈은 자동으로 분리되어 cfn-lint에 전달됩니다.

#### 방법 2: 옵션을 여러 번 사용

`--extra-lint-rules` 옵션을 여러 번 사용하여 여러 규칙 모듈을 지정할 수도 있습니다:

```bash
sam validate --lint --extra-lint-rules="module1.rules" --extra-lint-rules="module2.rules"
```

## 참고사항

* 과거에 사용하던 `--serverless-rules` 옵션은 deprecated 되었습니다. 
* 새로운 `--extra-lint-rules` 옵션을 사용하는 것이 좋습니다.
* 인스톨러로 SAM CLI를 설치한 경우 추가 규칙이 작동하지 않으면 인스톨러의 Python 환경에 패키지가 설치되어 있는지 확인하세요.
