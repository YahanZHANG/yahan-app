def article_input_text(article):
    """
    AIに渡す記事内容。

    媒体の利用規約に配慮し、記事ページの本文は取りに行かない。
    RSS や記事ページの紹介文（媒体が公開している短い説明）だけを使う。
    """

    return (
        article.summary_original
        or ""
    ).strip()
