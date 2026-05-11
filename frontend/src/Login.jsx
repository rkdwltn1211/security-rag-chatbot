import { useState } from "react"
import API_URL from "./api"

function Login({ onLogin }) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [isRegister, setIsRegister] = useState(false)

  const handleSubmit = async () => {
    if (!username.trim() || !password.trim()) {
      setError("아이디와 비밀번호를 입력해주세요.")
      return
    }

    setLoading(true)
    setError("")

    try {
      if (isRegister) {
        // 회원가입
        const res = await fetch(`${API_URL}/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password, role: "EMPLOYEE" })
        })
        const data = await res.json()
        if (!res.ok) {
          setError(data.detail || "회원가입 실패")
          return
        }
        setError("")
        setIsRegister(false)
        alert("회원가입 완료! 로그인해주세요.")
      } else {
        // 로그인
        const formData = new FormData()
        formData.append("username", username)
        formData.append("password", password)

        const res = await fetch(`${API_URL}/login`, {
          method: "POST",
          body: formData
        })
        const data = await res.json()
        if (!res.ok) {
          setError(data.detail || "로그인 실패")
          return
        }

        // 토큰 저장
        localStorage.setItem("token", data.access_token)
        localStorage.setItem("username", username)
        localStorage.setItem("role", data.role)
        onLogin(data.access_token, username, data.role)
      }
    } catch (e) {
        void e
      setError("서버 연결 실패. 서버를 확인해주세요.")
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleSubmit()
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        {/* 헤더 */}
        <div style={styles.header}>
          <div style={styles.icon}>🔒</div>
          <h1 style={styles.title}>IT 보안 정책 AI 어시스턴트</h1>
          <p style={styles.subtitle}>ISMS-P 문서 기반 Self-Correction RAG 시스템</p>
        </div>

        {/* 폼 */}
        <div style={styles.form}>
          <h2 style={styles.formTitle}>{isRegister ? "회원가입" : "로그인"}</h2>

          <input
            style={styles.input}
            type="text"
            placeholder="아이디"
            value={username}
            onChange={e => setUsername(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <input
            style={styles.input}
            type="password"
            placeholder="비밀번호"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={handleKeyDown}
          />

          {error && <p style={styles.error}>{error}</p>}

          <button
            style={loading ? styles.buttonDisabled : styles.button}
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? "처리 중..." : isRegister ? "회원가입" : "로그인"}
          </button>

          <p
            style={styles.toggle}
            onClick={() => { setIsRegister(!isRegister); setError("") }}
          >
            {isRegister ? "이미 계정이 있어요? 로그인" : "계정이 없어요? 회원가입"}
          </p>
        </div>
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#f0f2f5"
  },
  card: {
    backgroundColor: "white",
    borderRadius: "16px",
    boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
    width: "400px",
    overflow: "hidden"
  },
  header: {
    backgroundColor: "#1a1a2e",
    padding: "32px 24px",
    textAlign: "center",
    color: "white"
  },
  icon: {
    fontSize: "40px",
    marginBottom: "12px"
  },
  title: {
    margin: "0 0 8px",
    fontSize: "20px",
    fontWeight: "bold",
    color: "white"
  },
  subtitle: {
    margin: 0,
    fontSize: "12px",
    opacity: 0.7
  },
  form: {
    padding: "32px 24px",
    display: "flex",
    flexDirection: "column",
    gap: "12px"
  },
  formTitle: {
    margin: "0 0 8px",
    fontSize: "18px",
    color: "#1a1a2e"
  },
  input: {
    padding: "12px 16px",
    borderRadius: "8px",
    border: "1px solid #ddd",
    fontSize: "14px",
    outline: "none"
  },
  error: {
    margin: 0,
    color: "#e74c3c",
    fontSize: "13px"
  },
  button: {
    padding: "12px",
    backgroundColor: "#1a1a2e",
    color: "white",
    border: "none",
    borderRadius: "8px",
    fontSize: "15px",
    cursor: "pointer",
    marginTop: "4px"
  },
  buttonDisabled: {
    padding: "12px",
    backgroundColor: "#aaa",
    color: "white",
    border: "none",
    borderRadius: "8px",
    fontSize: "15px",
    cursor: "not-allowed",
    marginTop: "4px"
  },
  toggle: {
    textAlign: "center",
    color: "#666",
    fontSize: "13px",
    cursor: "pointer",
    margin: 0
  }
}

export default Login