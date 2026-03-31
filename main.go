package main

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"

	_ "modernc.org/sqlite"
)

type Result struct {
	Path string
	Hash string
	Err  error
}

func initDB(dbPath string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, err
	}
	statement := `
	CREATE TABLE IF NOT EXISTS media (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		path TEXT UNIQUE,
		hash TEXT,
		size INTEGER,
		embedding BLOB,
		indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);`
	_, err = db.Exec(statement)
	return db, err
}

func isAlreadyIndexed(db *sql.DB, path string) bool {
	var exists bool
	db.QueryRow("SELECT EXISTS(SELECT 1 FROM media WHERE path=?)", path).Scan(&exists)
	return exists
}

func hashFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	hasher := sha256.New()
	if _, err := io.Copy(hasher, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(hasher.Sum(nil)), nil
}

func worker(paths <-chan string, results chan<- Result, wg *sync.WaitGroup) {
	defer wg.Done()
	for path := range paths {
		hash, err := hashFile(path)
		results <- Result{Path: path, Hash: hash, Err: err}
	}
}

func main() {
	findDupes := flag.Bool("dupes", false, "")
	flag.Parse()
	root := flag.Arg(0)

	db, _ := initDB("media.db")
	defer db.Close()

	if *findDupes {
		rows, _ := db.Query(`SELECT hash, GROUP_CONCAT(path, ' | ') FROM media GROUP BY hash HAVING COUNT(hash) > 1`)
		defer rows.Close()
		for rows.Next() {
			var hash, paths string
			rows.Scan(&hash, &paths)
			fmt.Println("DUPE:", hash[:8], paths)
		}
		return
	}

	if root == "" {
		fmt.Println("usage: go run main.go [-dupes] <dir>")
		return
	}

	numWorkers := runtime.NumCPU()
	paths := make(chan string, 100)
	results := make(chan Result, 100)
	done := make(chan bool)
	var wg sync.WaitGroup

	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go worker(paths, results, &wg)
	}

	go func() {
		for res := range results {
			if res.Err != nil {
				fmt.Println("ERROR:", res.Path)
				continue
			}
			info, _ := os.Stat(res.Path)
			db.Exec("INSERT OR REPLACE INTO media (path, hash, size) VALUES (?, ?, ?)", res.Path, res.Hash, info.Size())
			fmt.Println("HASHED:", res.Path)
		}
		done <- true
	}()

	filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		if ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".mp4" {
			if isAlreadyIndexed(db, path) {
				fmt.Println("SKIPPED:", path)
				return nil
			}
			paths <- path
		}
		return nil
	})

	close(paths)
	wg.Wait()
	close(results)
	<-done
	fmt.Println("DONE")
}
