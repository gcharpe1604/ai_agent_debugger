import { createContext, useContext } from 'react'

// The signed-in account on the durable source: { user, adapter, setUser, signOut }.
// null in the local profile and in fixture tests, where there are no accounts.
export const AccountContext = createContext(null)
export const useAccount = () => useContext(AccountContext)
