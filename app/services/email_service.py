import boto3
from botocore.exceptions import ClientError
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, aws_region: str, access_key: str, secret_key: str, from_email: str):
        self.aws_region = aws_region
        self.from_email = from_email
        
        # Initialize SES client
        self.ses_client = boto3.client(
            'ses',
            region_name=aws_region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
    
    async def send_verification_code_email(self, email: str, code: str) -> None:
        """이메일 인증 코드 발송"""
        subject = "이메일 인증 코드"
        body_text = f"""
안녕하세요!

이메일 인증 코드는 다음과 같습니다:

인증 코드: {code}

이 코드는 10분 후에 만료됩니다.

감사합니다.
        """
        
        body_html = f"""
<html>
<head></head>
<body>
    <h2>이메일 인증 코드</h2>
    <p>안녕하세요!</p>
    <p>이메일 인증 코드는 다음과 같습니다:</p>
    <h3 style="color: #007bff;">인증 코드: {code}</h3>
    <p>이 코드는 10분 후에 만료됩니다.</p>
    <p>감사합니다.</p>
</body>
</html>
        """
        
        await self._send_email(email, subject, body_text, body_html)
    
    async def send_password_reset_email(self, email: str, reset_token: str) -> None:
        """비밀번호 재설정 이메일 발송"""
        reset_url = f"https://yourdomain.com/reset-password?token={reset_token}"
        
        subject = "비밀번호 재설정 요청"
        body_text = f"""
안녕하세요!

비밀번호 재설정을 요청하셨습니다.

아래 링크를 클릭하여 새로운 비밀번호를 설정해주세요:
{reset_url}

이 링크는 1시간 후에 만료됩니다.

만약 비밀번호 재설정을 요청하지 않으셨다면, 이 이메일을 무시해주세요.

감사합니다.
        """
        
        body_html = f"""
<html>
<head></head>
<body>
    <h2>비밀번호 재설정 요청</h2>
    <p>안녕하세요!</p>
    <p>비밀번호 재설정을 요청하셨습니다.</p>
    <p>아래 버튼을 클릭하여 새로운 비밀번호를 설정해주세요:</p>
    <p>
        <a href="{reset_url}" 
           style="background-color: #007bff; color: white; padding: 10px 20px; 
                  text-decoration: none; border-radius: 4px; display: inline-block;">
            비밀번호 재설정
        </a>
    </p>
    <p>또는 다음 링크를 복사하여 브라우저에 붙여넣으세요:</p>
    <p>{reset_url}</p>
    <p>이 링크는 1시간 후에 만료됩니다.</p>
    <p>만약 비밀번호 재설정을 요청하지 않으셨다면, 이 이메일을 무시해주세요.</p>
    <p>감사합니다.</p>
</body>
</html>
        """
        
        await self._send_email(email, subject, body_text, body_html)
    
    async def _send_email(self, recipient: str, subject: str, body_text: str, body_html: str) -> None:
        """AWS SES를 통해 이메일 발송"""
        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={
                    'ToAddresses': [recipient]
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': body_text,
                            'Charset': 'UTF-8'
                        },
                        'Html': {
                            'Data': body_html,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )
            
            logger.info(f"Email sent successfully to {recipient}. Message ID: {response['MessageId']}")
            
        except ClientError as e:
            logger.error(f"Failed to send email to {recipient}: {str(e)}")
            raise Exception(f"Failed to send email: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error sending email to {recipient}: {str(e)}")
            raise Exception(f"Failed to send email: {str(e)}")