import { useState, useRef } from "react"
import Login from "./Login"
import Dashboard from "./Dashboard"
import API_URL from "./api"


function App() {
// 변경
  const [token, setToken] = useState(localStorage.getItem("token") || "")
  const [username, setUsername] = useState(localStorage.getItem("username") || "")
  const [role, setRole] = useState(localStorage.getItem("role") || "")
  console.log("token 값:", token)
  const [question, setQuestion] = useState("")
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const lastAiMessageRef = useRef(null)
  const [showDashboard, setShowDashboard] = useState(false)

  // 로그인 처리
  const handleLogin = (newToken, newUsername, newRole) => {
    localStorage.setItem("token", newToken)       // ← 추가
    localStorage.setItem("username", newUsername) // ← 추가
    localStorage.setItem("role", newRole)         // ← 추가
    setToken(newToken)
    setUsername(newUsername)
    setRole(newRole)
  }

    // 로그인 안 됐으면 로그인 화면
  if (!token) return <Login onLogin={handleLogin} />

  // ADMIN이면 대시보드 보여주기
  if (showDashboard) return (
    <Dashboard token={token} onBack={() => setShowDashboard(false)} />
  )

  // 로그아웃 처리
  const handleLogout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("username")
    localStorage.removeItem("role")
    setToken("")
    setUsername("")
    setRole("")
    setMessages([])
  }

  const handleAsk = async () => {
    if (!question.trim()) return

    const userMessage = { role: "user", content: question }
    setMessages(prev => [...prev, userMessage])
    setQuestion("")
    setLoading(true)

    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ question })
      })

      if (response.status === 401) {
        handleLogout()
        return
      }

      const data = await response.json()
      const aiMessage = {
        role: "assistant",
        content: data.answer,
        sources: data.sources
      }
      setMessages(prev => [...prev, aiMessage])

      setTimeout(() => {
        lastAiMessageRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
      }, 100)

    } catch (e) {
      void e
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "오류가 발생했습니다. 서버를 확인해주세요.",
        sources: ""
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleAsk()
    }
  }



  return (
    <div style={styles.container}>
      {/* 헤더 */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.headerTitle}>🔒 IT 보안 정책 AI 어시스턴트</h1>
          <p style={styles.headerSubtitle}>ISMS-P 문서 기반 Self-Correction RAG 시스템</p>
        </div>
        <div style={styles.userInfo}>
          <span style={styles.userName}>👤 {username}</span>
          <span style={styles.userRole}>{role}</span>
          {role === "ADMIN" && (
            <button style={styles.dashboardButton} onClick={() => setShowDashboard(true)}>
              📊 대시보드
            </button>
          )}  
          <button style={styles.logoutButton} onClick={handleLogout}>로그아웃</button>
        </div>
      </div>

      {/* 채팅 영역 */}
      <div style={styles.chatBox}>
        {messages.length === 0 && (
          <div style={styles.emptyState}>
            <p>💬 보안 정책에 대해 질문해보세요!</p>
            <p style={styles.emptyHint}>예) "랜섬웨어 감염 시 어떻게 대응해야 하나요?"</p>
            <p style={styles.emptyHint}>예) "비밀번호 규정이 어떻게 되나요?"</p>
            <p style={styles.emptyHint}>예) "개인정보 유출 시 신고 의무가 있나요?"</p>
          </div>
        )}

      {messages.map((msg, idx) => {
      // 경고 메시지 감지
      const isWarning = msg.role === "assistant" && (
        msg.content.includes("찾을 수 없") ||
        msg.content.includes("제공할 수 없") ||
        msg.content.includes("접근 가능한 문서에서")
      )

      return (
        <div
          key={idx}
          ref={msg.role === "assistant" && idx === messages.length - 1 ? lastAiMessageRef : null}
          style={msg.role === "user" ? styles.userBubbleWrap : styles.aiBubbleWrap}
        >
          <div style={msg.role === "user" ? styles.userBubble : isWarning ? styles.warningBubble : styles.aiBubble}>
            <p style={styles.bubbleText}>{msg.content}</p>
            {msg.sources && (
              <div style={styles.sources}>
                <p style={styles.sourcesTitle}>📚 출처</p>
                <p style={styles.sourcesText}>{msg.sources}</p>
              </div>
            )}
          </div>
        </div>
      )
})}

        {loading && (
          <div style={styles.aiBubbleWrap}>
            <div style={styles.aiBubble}>
              <p style={styles.bubbleText}>🔍 문서 검색 및 검증 중...</p>
            </div>
          </div>
        )}
      </div>

      {/* 입력 영역 */}
      <div style={styles.inputArea}>
        <textarea
          style={styles.input}
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="보안 정책에 대해 질문하세요... (Enter로 전송)"
          rows={2}
        />
        <button
          style={loading ? styles.buttonDisabled : styles.button}
          onClick={handleAsk}
          disabled={loading}
        >
          {loading ? "⏳" : "전송"}
        </button>
      </div>
    </div>
  )
}

const styles = {
  container: {
    maxWidth: "800px",
    margin: "0 auto",
    height: "100vh",
    display: "flex",
    flexDirection: "column",
    fontFamily: "sans-serif",
    backgroundColor: "#f5f5f5"
  },
  header: {
    backgroundColor: "#1a1a2e",
    color: "white",
    padding: "16px 20px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center"
  },
  headerTitle: {
    margin: 0,
    fontSize: "18px",
    color: "white"
  },
  headerSubtitle: {
    margin: "4px 0 0",
    fontSize: "11px",
    opacity: 0.7
  },
  userInfo: {
    display: "flex",
    alignItems: "center",
    gap: "8px"
  },
  userName: {
    fontSize: "13px"
  },
  userRole: {
    fontSize: "11px",
    backgroundColor: "#2a2a4e",
    padding: "2px 8px",
    borderRadius: "10px"
  },
  logoutButton: {
    padding: "4px 10px",
    backgroundColor: "transparent",
    color: "white",
    border: "1px solid rgba(255,255,255,0.3)",
    borderRadius: "6px",
    fontSize: "12px",
    cursor: "pointer"
  },
  chatBox: {
    flex: 1,
    overflowY: "auto",
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "12px"
  },
  emptyState: {
    textAlign: "center",
    color: "#888",
    marginTop: "60px",
    fontSize: "15px"
  },
  emptyHint: {
    fontSize: "13px",
    color: "#aaa",
    margin: "6px 0"
  },
  userBubbleWrap: {
    display: "flex",
    justifyContent: "flex-end"
  },
  aiBubbleWrap: {
    display: "flex",
    justifyContent: "flex-start"
  },
  userBubble: {
    backgroundColor: "#4a90d9",
    color: "white",
    padding: "12px 16px",
    borderRadius: "18px 18px 4px 18px",
    maxWidth: "70%"
  },
  aiBubble: {
    backgroundColor: "white",
    color: "#333",
    padding: "12px 16px",
    borderRadius: "18px 18px 18px 4px",
    maxWidth: "80%",
    boxShadow: "0 1px 4px rgba(0,0,0,0.1)"
  },
  bubbleText: {
    margin: 0,
    fontSize: "14px",
    lineHeight: "1.6",
    whiteSpace: "pre-wrap"
  },
  sources: {
    marginTop: "10px",
    paddingTop: "10px",
    borderTop: "1px solid #eee"
  },
  sourcesTitle: {
    margin: "0 0 4px",
    fontSize: "12px",
    fontWeight: "bold",
    color: "#666"
  },
  sourcesText: {
    margin: 0,
    fontSize: "12px",
    color: "#888",
    whiteSpace: "pre-wrap"
  },
  inputArea: {
    display: "flex",
    gap: "10px",
    padding: "16px",
    backgroundColor: "white",
    borderTop: "1px solid #ddd"
  },
  input: {
    flex: 1,
    padding: "10px 14px",
    borderRadius: "10px",
    border: "1px solid #ddd",
    fontSize: "14px",
    resize: "none",
    outline: "none"
  },
  button: {
    padding: "10px 20px",
    backgroundColor: "#1a1a2e",
    color: "white",
    border: "none",
    borderRadius: "10px",
    fontSize: "14px",
    cursor: "pointer"
  },
  buttonDisabled: {
    padding: "10px 20px",
    backgroundColor: "#aaa",
    color: "white",
    border: "none",
    borderRadius: "10px",
    fontSize: "14px",
    cursor: "not-allowed"
  },

  warningBubble: {
    backgroundColor: "#fffbe6",
    color: "#7d6608",
    padding: "12px 16px",
    borderRadius: "18px 18px 18px 4px",
    maxWidth: "80%",
    boxShadow: "0 1px 4px rgba(0,0,0,0.1)",
    border: "1px solid #ffe58f"
}
}

export default App